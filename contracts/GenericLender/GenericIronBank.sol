// SPDX-License-Identifier: GPL-3.0
pragma solidity >=0.6.12;
pragma experimental ABIEncoderV2;

import "../Interfaces/Compound/CErc20I.sol";
import "../Interfaces/Compound/InterestRateModel.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/math/SafeMath.sol";
import "@openzeppelin/contracts/utils/Address.sol";
import "@openzeppelin/contracts/token/ERC20/SafeERC20.sol";
import "../Interfaces/Balancer/IBalancerVault.sol";
import "../Interfaces/Ironbank/IStakingRewards.sol";
import "../Interfaces/Ironbank/IStakingRewardsFactory.sol";
import "./GenericLenderBase.sol";

/********************
 *   A lender plugin for LenderYieldOptimiser for any erc20 asset on compound (not eth)
 *   Made by SamPriestley.com
 *   https://github.com/Grandthrax/yearnv2/blob/master/contracts/GenericDyDx/GenericCompound.sol
 *
 ********************* */

contract GenericIronBank is GenericLenderBase {
    using SafeERC20 for IERC20;
    using Address for address;
    using SafeMath for uint256;

    uint256 private constant blocksPerYear = 3154 * 10**4;
    address public constant ib = address(0x00a35FD824c717879BF370E70AC6868b95870Dfb);
    
    IStakingRewards public stakingRewards;
    IStakingRewardsFactory public constant rewardsFactory =
        IStakingRewardsFactory(0x35F70CE60f049A8c21721C53a1dFCcB5bF4a1Ea8);

    /*** 
        Rewards token stuff
    ***/
    //Wrapped native token for chain i.e. WETH
    address public constant WNATIVE =
        0x4200000000000000000000000000000000000006;
    //USDC for the middle of swaps
    address internal constant usdc = 0x7F5c764cBc14f9669B88837ca1490cCa17c31607;
    //Asset to use for swap as the middle
    address public middleSwapToken;
    //stable bool should be true if we are using usdc as the middle token and want is a stable coin
    bool public stable;
    ///For Optimism we will only be using the Veledrome router \\\\
    IVeledrome public constant router =
        IVeledrome(0xa132DAB612dB5cB9fC9Ac426A0Cc215A3423F9c9);

    IBalancerVault public constant balancerVault =
        IBalancerVault(0xBA12222222228d8Ba445958a75a0704d566BF2C8);

    address public tradeFactory;
  
    uint256 public dustThreshold;

    bool public ignorePrinting;

    uint256 public minIbToSell = 0 ether;

    CErc20I public cToken;

    constructor(
        address _strategy,
        string memory name
    ) public GenericLenderBase(_strategy, name) {
        _initialize(_cToken);
    }

    function initialize(address _cToken) external {
        _initialize(_cToken);
    }

    function _initialize(address _cToken) internal {
        require(address(cToken) == address(0), "GenericIB already initialized");
        cToken = CErc20I(rewardsFactory.getStakingToken(address(want)));
        stakingRewards = IStakingRewards(rewardsFactory.getStakingRewards(address(cToken)));
        require(cToken.underlying() == address(want), "WRONG CTOKEN");
        want.safeApprove(_cToken, type(uint256).max);
        IERC20(ib).safeApprove(address(router), type(uint256).max);
        dustThreshold = 1_000; //depends on want
    }

    function cloneCompoundLender(
        address _strategy,
        string memory _name,
        address _cToken
    ) external returns (address newLender) {
        newLender = _clone(_strategy, _name);
        GenericIronBank(newLender).initialize(_cToken);
    }

    function nav() external view override returns (uint256) {
        return _nav();
    }

    //adjust dust threshol
    function setDustThreshold(uint256 amount) external management {
        dustThreshold = amount;
    }

    //Can update the staking rewards contract, May start as 0 if not rewarded then changes later
    function setStakingRewards() external management {
        stakingRewards = IStakingRewards(rewardsFactory.getStakingRewards(address(cToken)));
    }

    function setRewardStuff(uint256 _minIbToSell, uint256 _minRewardToHavest) external management {
        minIbToSell = _minIbToSell;
        minRewardToHarvest = _minRewardToHavest;
    }

    //adjust dust threshol
    function setIgnorePrinting(bool _ignorePrinting) external management {
        ignorePrinting = _ignorePrinting;
    }

    function _nav() internal view returns (uint256) {
        uint256 amount = want.balanceOf(address(this)).add(underlyingBalanceStored());

        if(amount < dustThreshold){
            return 0;
        }else{
            return amount;
        }
    }

    function underlyingBalanceStored() public view returns (uint256 balance) {
        uint256 currentCr = cToken.balanceOf(address(this)).add(stakedBalance());
        if (currentCr < dustThreshold) {
            balance = 0;
        } else {
            //The current exchange rate as an unsigned integer, scaled by 1e18.
            balance = currentCr.mul(cToken.exchangeRateStored()).div(1e18);
        }
    }

    function stakedBalance() public view returns(uint256) {
        if(address(stakingRewards) == address(0)) return 0;

        return stakingRewards.balanceOf(address(this));
    }

    function apr() external view override returns (uint256) {
        return _apr();
    }

    function _apr() internal view returns (uint256) {
        return (cToken.supplyRatePerBlock().add(compBlockShareInWant(0, false))).mul(blocksPerYear);
    }

    function compBlockShareInWant(uint256 change, bool add) public view returns (uint256){

        if(ignorePrinting){
            return 0;
        }
        //comp speed is amount to borrow or deposit (so half the total distribution for want)
        //uint256 distributionPerBlock = ComptrollerI(unitroller).compSpeeds(address(cToken));
        (uint distributionPerBlock, , uint supplyEnd) = liquidityMining.rewardSupplySpeeds(ib, address(cToken));
        if(supplyEnd < block.timestamp){
            return 0;
        }
        //convert to per dolla
        uint256 totalSupply = cToken.totalSupply().mul(cToken.exchangeRateStored()).div(1e18);
        if(add){
            totalSupply = totalSupply.add(change);
        }else{
            totalSupply = totalSupply.sub(change);
        }

        uint256 blockShareSupply = 0;
        if(totalSupply > 0){
            blockShareSupply = distributionPerBlock.mul(1e18).div(totalSupply);
        }

        uint256 estimatedWant =  priceCheck(ib, address(want),blockShareSupply);
        uint256 compRate;
        if(estimatedWant != 0){
            compRate = estimatedWant.mul(9).div(10); //10% pessimist

        }

        return(compRate);
    }

    //WARNING. manipulatable and simple routing. Only use for safe functions
    function priceCheck(address start, address end, uint256 _amount) public view returns (uint256) {
        if (_amount == 0) {
            return 0;
        }
        uint256[] memory amounts = router.getAmountsOut(_amount, getTokenOutPath(start, end));

        return amounts[amounts.length - 1];
    }

    function weightedApr() external view override returns (uint256) {
        uint256 a = _apr();
        return a.mul(_nav());
    }

    function withdraw(uint256 amount) external override management returns (uint256) {
        return _withdraw(amount);
    }

    //emergency withdraw. sends balance plus amount to governance
    function emergencyWithdraw(uint256 amount) external override management {
        //dont care about errors here. we want to exit what we can
        cToken.redeem(amount);

        want.safeTransfer(vault.governance(), want.balanceOf(address(this)));
    }

    //withdraw an amount including any want balance
    function _withdraw(uint256 amount) internal returns (uint256) {
        uint256 balanceUnderlying = cToken.balanceOfUnderlying(address(this));
        uint256 looseBalance = want.balanceOf(address(this));
        uint256 total = balanceUnderlying.add(looseBalance);

        if (amount.add(dustThreshold) >= total) {
            //cant withdraw more than we own. so withdraw all we can
            if(balanceUnderlying > dustThreshold){
                require(cToken.redeem(cToken.balanceOf(address(this))) == 0, "ctoken: redeemAll fail");
            }
            looseBalance = want.balanceOf(address(this));
            if(looseBalance > 0 ){
                want.safeTransfer(address(strategy), looseBalance);
                return looseBalance;
            }else{
                return 0;
            }

        }

        if (looseBalance >= amount) {
            want.safeTransfer(address(strategy), amount);
            return amount;
        }

        //not state changing but OK because of previous call
        uint256 liquidity = want.balanceOf(address(cToken));

        if (liquidity > 1) {
            uint256 toWithdraw = amount.sub(looseBalance);

            if (toWithdraw > liquidity) {
                toWithdraw = liquidity;
            }
            if(toWithdraw > dustThreshold){
                require(cToken.redeemUnderlying(toWithdraw) == 0, "ctoken: redeemUnderlying fail");
            }

        }
        if(!ignorePrinting){
            _disposeOfComp();
        }

        looseBalance = want.balanceOf(address(this));
        want.safeTransfer(address(strategy), looseBalance);
        return looseBalance;
    }

    function manualClaimAndDontSell() external management{
        stakingRewards.getReward();
    }

    function harvest() external keepers {
        _disposeOfComp();

        uint256 wantBalance = want.balanceOf(address(this));
        if(wantBalance > 0) {
            cToken.mint(wantBalance);
        }
        stake();
    }

    function harvestTrigger(uint256 /*callCost*/) external view returns(bool) {
        if(address(stakingRewards) == address(0)) return false;

        if(getRewardsOwed().add(IERC20(ib).balanceOf(address(this))) >= minRewardToHarvest) return true;
    }

    function getRewardsOwed() public view returns(uint256) {
        return stakingRewards.earned(ib, address(this));
    }

    function _disposeOfComp() internal {
        if(address(stakingRewards) != address(0)){
            stakingRewards.getReward();
        }

        uint256 _ib = IERC20(ib).balanceOf(address(this));

        if (_ib > minIbToSell && tradeFactory == address(0)) {
            _swapFrom(ib, address(want), _ib);
        }
    }

    function _swapFrom(address _from, address _to, uint256 _amountIn) internal{
    

        router.swapExactTokensForTokens(
            _amountIn, 
            0, 
            getTokenOutPath(_from, _to), 
            address(this), 
            block.timestamp
        );
    }

    function getTokenOutPath(address _tokenIn, address _tokenOut) internal view returns (IVeledrome.route[] memory _path) {
        bool isNative = _tokenIn == middleSwapToken || _tokenOut == middleSwapToken;
        _path = new IVeledrome.route[](isNative ? 1 : 2);

        if (isNative) {
            _path[0] = IVeledrome.route(
                _tokenIn,
                _tokenOut,
                false
            );
        } else {
            _path[0] = IVeledrome.route(
                _tokenIn,
                middleSwapToken,
                false
            );
            _path[1] = IVeledrome.route(
                middleSwapToken,
                _tokenOut,
                stable
            );
        }
    }

    //External function to change the token we use for swaps and the bool for the second route in path
    //Can only change to either the native or USDC.
    function setMiddleSwapToken(address _middleSwapToken, bool _stable) external management {
        require(_middleSwapToken == WNATIVE || _middleSwapToken == usdc);
        middleSwapToken = _middleSwapToken;
        stable = _stable;
    }

    function deposit() external override management {
        uint256 balance = want.balanceOf(address(this));
        require(cToken.mint(balance) == 0, "ctoken: mint fail");
        stake();
    }

    function stake() internal {
        uint256 balance = cToken.balanceOf(address(this));
        if(stakingRewards == address(0) || balance == 0) return;

        stakingRewards.stake(balance);
    }

    function withdrawAll() external override management returns (bool) {
        uint256 liquidity = want.balanceOf(address(cToken));
        uint256 liquidityInCTokens = convertFromUnderlying(liquidity);
        uint256 amountInCtokens = cToken.balanceOf(address(this));  /// NNEEE TP UNSTAKE GERE 

        bool all;

        if (liquidityInCTokens > 2) {
            liquidityInCTokens = liquidityInCTokens-1;

            if (amountInCtokens <= liquidityInCTokens) {
                //we can take all
                all = true;
                cToken.redeem(amountInCtokens);
            } else {
                //redo or else price changes
                cToken.mint(0);
                liquidityInCTokens = convertFromUnderlying(want.balanceOf(address(cToken)));
                //take all we can
                all = false;
                cToken.redeem(liquidityInCTokens);
            }
        }

        uint256 looseBalance = want.balanceOf(address(this));
        if(looseBalance > 0){
            want.safeTransfer(address(strategy), looseBalance);
        }
        return all;

    }

    function convertFromUnderlying(uint256 amountOfUnderlying) public view returns (uint256 balance){
        if (amountOfUnderlying == 0) {
            balance = 0;
        } else {
            balance = amountOfUnderlying.mul(1e18).div(cToken.exchangeRateStored());
        }
    }

    function hasAssets() external view override returns (bool) {
        return underlyingBalanceStored() > dustThreshold || want.balanceOf(address(this)) > 0;
    }

    function aprAfterDeposit(uint256 amount) external view override returns (uint256) {
        uint256 cashPrior = want.balanceOf(address(cToken));

        uint256 borrows = cToken.totalBorrows();

        uint256 reserves = cToken.totalReserves();

        uint256 reserverFactor = cToken.reserveFactorMantissa();

        InterestRateModel model = cToken.interestRateModel();

        //the supply rate is derived from the borrow rate, reserve factor and the amount of total borrows.
        uint256 supplyRate = model.getSupplyRate(cashPrior.add(amount), borrows, reserves, reserverFactor);
        supplyRate = supplyRate.add(compBlockShareInWant(amount, true));

        return supplyRate.mul(blocksPerYear);
    }

    function protectedTokens() internal view override returns (address[] memory) {}

    // ---------------------- YSWAPS FUNCTIONS ----------------------
    function setTradeFactory(address _tradeFactory) external onlyGovernance {
        if (tradeFactory != address(0)) {
            _removeTradeFactoryPermissions();
        }

        ITradeFactory tf = ITradeFactory(_tradeFactory);

        IERC20(ib).safeApprove(_tradeFactory, type(uint256).max);
        tf.enable(comp, address(want));
        
        tradeFactory = _tradeFactory;
    }

    function removeTradeFactoryPermissions() external management {
        _removeTradeFactoryPermissions();
    }

    function _removeTradeFactoryPermissions() internal {
        IERC20(ib).safeApprove(tradeFactory, 0);
        
        tradeFactory = address(0);
    }
}