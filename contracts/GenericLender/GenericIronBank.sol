// SPDX-License-Identifier: GPL-3.0
pragma solidity >=0.6.12;
pragma experimental ABIEncoderV2;

import "../Interfaces/Compound/CErc20I.sol";
import "../Interfaces/Compound/InterestRateModel.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/math/SafeMath.sol";
import "@openzeppelin/contracts/utils/Address.sol";
import "@openzeppelin/contracts/token/ERC20/SafeERC20.sol";
import "@openzeppelin/contracts/math/Math.sol";
import "../Interfaces/Balancer/IBalancerVault.sol";
import "../Interfaces/Ironbank/IStakingRewards.sol";
import "../Interfaces/Ironbank/IStakingRewardsFactory.sol";
import "../Interfaces/ySwaps/ITradeFactory.sol";
import "./GenericLenderBase.sol";

/********************
 *   A lender plugin for LenderYieldOptimiser for any erc20 asset on IronBank (not eth)
 *   Made by @Schlagonia
 *   https://github.com/Schlagonia/Yearn-V2-Generic-Lender/blob/main/contracts/GenericLender/GenericIronBank.sol
 *
 ********************* */

interface IVeledrome {
    struct route {
        address from;
        address to;
        bool stable;
    }
    
    function swapExactTokensForTokens(
        uint amountIn,
        uint amountOutMin,
        route[] calldata routes,
        address to,
        uint deadline
    ) external returns (uint256[] memory amounts);

    function getAmountsOut(uint amountIn, route[] memory routes) external view returns (uint256[] memory amounts);
} 

contract GenericIronBank is GenericLenderBase {
    using SafeERC20 for IERC20;
    using Address for address;
    using SafeMath for uint256;

    //Seconds per year for calculations
    uint256 private constant blocksPerYear = 3154 * 10**4;
    //Reward token
    address public constant ib = 
        0x00a35FD824c717879BF370E70AC6868b95870Dfb;
    
    //Contracts for staking i tokens
    IStakingRewards public stakingRewards;
    IStakingRewardsFactory public constant rewardsFactory =
        IStakingRewardsFactory(0x35F70CE60f049A8c21721C53a1dFCcB5bF4a1Ea8);

    /*** 
        Rewards token stuff
    ***/
    //Wrapped native token for chain i.e. WETH
    address internal constant WNATIVE =
        0x4200000000000000000000000000000000000006;
    //USDC for the middle of swaps
    address internal constant usdc = 
        0x7F5c764cBc14f9669B88837ca1490cCa17c31607;
    //Asset to use for swap as the middle
    address public middleSwapToken;
    //stable bool should be true if we are using usdc as the middle token and want is a stable coin
    bool public stable;
    ///For Optimism we will only be using the Veledrome router \\\\
    IVeledrome public constant router =
        IVeledrome(0xa132DAB612dB5cB9fC9Ac426A0Cc215A3423F9c9);
    //Balancer Variables for swapping
    IBalancerVault public constant balancerVault =
        IBalancerVault(0xBA12222222228d8Ba445958a75a0704d566BF2C8);
    bytes32 public constant ibEthPoolId = 
        bytes32(0xefb0d9f51efd52d7589a9083a6d0ca4de416c24900020000000000000000002c);
    //Can be set for a weth - want lp balncer pool to make harvests work
    bytes32 public ethWantPoolId;

    address public keep3r;
    address public tradeFactory;
    bool public ignorePrinting;

    uint256 public dustThreshold;
    uint256 public minIbToSell;
    uint256 public minRewardToHarvest;

    CErc20I public cToken;

    constructor(
        address _strategy,
        string memory name
    ) public GenericLenderBase(_strategy, name) {
        _initialize();
    }

    function initialize() external {
        _initialize();
    }

    function _initialize() internal {
        require(address(cToken) == address(0), "GenericIB already initialized");
        cToken = CErc20I(rewardsFactory.getStakingToken(address(want)));
        require(cToken.underlying() == address(want), "WRONG CTOKEN");

        address _stakingRewards = rewardsFactory.getStakingRewards(address(cToken));
        if(_stakingRewards != address(0)) {
            cToken.approve(_stakingRewards, type(uint256).max);
            stakingRewards = IStakingRewards(_stakingRewards);
        }

        want.safeApprove(address(cToken), type(uint256).max);

        //default to usdc
        middleSwapToken = usdc;
        //default to ignore printing due to lack of IB liquidity
        ignorePrinting = true;
        dustThreshold = 1_000; //depends on want
    }

    function cloneIronBankLender(
        address _strategy,
        string memory _name
    ) external returns (address newLender) {
        newLender = _clone(_strategy, _name);
        GenericIronBank(newLender).initialize();
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
        address _stakingRewards = rewardsFactory.getStakingRewards(address(cToken));
        if(_stakingRewards != address(0)){
            cToken.approve(address(stakingRewards), 0);
            cToken.approve(_stakingRewards, type(uint256).max);
            //make sure ignorePrinting == true
            ignorePrinting = true;
        }
        stakingRewards = IStakingRewards(_stakingRewards);
    }

    function setRewardStuff(bytes32 _ethWantPoolId, uint256 _minIbToSell, uint256 _minRewardToHavest) external management {
        ethWantPoolId = _ethWantPoolId;
        minIbToSell = _minIbToSell;
        minRewardToHarvest = _minRewardToHavest;
    }

    //adjust dust threshol
    function setIgnorePrinting(bool _ignorePrinting) external management {
        ignorePrinting = _ignorePrinting;
    }

    function setKeep3r(address _keep3r) external management {
        keep3r = _keep3r;
    }

    function balanceOfWant() public view returns(uint256) {
        return want.balanceOf(address(this));
    }

    function balanceOfCToken() public view returns(uint256) {
        return cToken.balanceOf(address(this));
    }

    function _nav() internal view returns (uint256) {
        uint256 amount = balanceOfWant().add(underlyingBalanceStored());

        if(amount < dustThreshold){
            return 0;
        }else{
            return amount;
        }
    }

    function underlyingBalanceStored() public view returns (uint256 balance) {
        uint256 currentCr = balanceOfCToken().add(stakedBalance());
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
        return (cToken.supplyRatePerBlock().add(compBlockShareInWant(0))).mul(blocksPerYear);
    }

    function compBlockShareInWant(uint256 change) public view returns (uint256){

        if(ignorePrinting){
            return 0;
        }

        if(stakingRewards.periodFinish() < block.timestamp){
            return 0;
        }
        uint256 distributionPerSec = stakingRewards.getRewardRate(ib);
        //convert to per dolla
        uint256 totalStaked = stakingRewards.totalSupply().mul(cToken.exchangeRateStored()).div(1e18);
        
        totalStaked = totalStaked.add(change);

        uint256 blockShareSupply;
        if(totalStaked > 0){
            blockShareSupply = distributionPerSec.mul(1e18).div(totalStaked);
        }

        uint256 estimatedWant = _priceCheck(ib, address(want), blockShareSupply);
        uint256 compRate;
        if(estimatedWant != 0){
            compRate = estimatedWant.mul(9).div(10); //10% pessimist
        }

        return(compRate);
    }

    //WARNING. manipulatable and simple routing. Only use for safe functions
    function _priceCheck(address start, address end, uint256 _amount) internal view returns (uint256) {
        if (_amount == 0) {
            return 0;
        }
        uint256[] memory amounts = router.getAmountsOut(_amount, _getTokenOutPath(start, end));

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
        _unStake(_convertFromUnderlying(amount));
        cToken.redeemUnderlying(amount);

        want.safeTransfer(vault.governance(), balanceOfWant());
    }

    //withdraw an amount including any want balance
    function _withdraw(uint256 amount) internal returns (uint256) {
        //Call to accrue rewards and update exchange rate first
        cToken.accrueInterest();
        //This should be accurate due to previous call
        uint256 balanceUnderlying = underlyingBalanceStored();
        uint256 looseBalance = balanceOfWant();
        uint256 total = balanceUnderlying.add(looseBalance);

        if (amount >= total) {
            //cant withdraw more than we own. so withdraw all we can
            if(balanceUnderlying > dustThreshold){
                _unStake(stakedBalance());
                require(cToken.redeem(balanceOfCToken()) == 0, "ctoken: redeemAll fail");
            }
            looseBalance = balanceOfWant();
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
            if(toWithdraw > 0){
                _unStake(_convertFromUnderlying(toWithdraw));
                require(cToken.redeemUnderlying(toWithdraw) == 0, "ctoken: redeemUnderlying fail");
            }
        }

        looseBalance = balanceOfWant();
        want.safeTransfer(address(strategy), looseBalance);
        return looseBalance;
    }

    function manualClaimAndDontSell() external management{
        stakingRewards.getReward();
    }

    function harvest() external keepers {
        _disposeOfComp();

        uint256 wantBalance = balanceOfWant();
        if(wantBalance > 0) {
            cToken.mint(wantBalance);
        }
        _stake();
    }

    function harvestTrigger(uint256 /*callCost*/) external view returns(bool) {
        if(address(stakingRewards) == address(0)) return false;

        if(getRewardsOwed().add(IERC20(ib).balanceOf(address(this))) > minRewardToHarvest) return true;
    }

    function getRewardsOwed() public view returns(uint256) {
        return stakingRewards.earned(ib, address(this));
    }

    function _disposeOfComp() internal {
        if(address(stakingRewards) != address(0) && stakedBalance() > 0){
            stakingRewards.getReward();
        }

        uint256 _ib = IERC20(ib).balanceOf(address(this));

        if (_ib > minIbToSell && tradeFactory == address(0)) {
            _swapFrom(ib, address(want), _ib);
        }
    }

    function _swapFrom(address _from, address _to, uint256 _amountIn) internal{
        IBalancerVault.BatchSwapStep[] memory swaps;
        IAsset[] memory assets;
        int[] memory limits;
        if(address(want) == WNATIVE) {
            swaps = new IBalancerVault.BatchSwapStep[](1);
            assets = new IAsset[](2);
            limits = new int[](2);
        } else{
            swaps = new IBalancerVault.BatchSwapStep[](2);
            assets = new IAsset[](3);
            limits = new int[](3);
            //Sell WETH -> want
            swaps[1] = IBalancerVault.BatchSwapStep(
                ethWantPoolId,
                1,
                2,
                0,
                abi.encode(0)
            );
            assets[2] = IAsset(address(want));
        }
        
        //Sell ib -> weth
        swaps[0] = IBalancerVault.BatchSwapStep(
            ibEthPoolId,
            0,
            1,
            _amountIn,
            abi.encode(0)
        );

        //Match the token address with the desired index for this trade
        assets[0] = IAsset(ib);
        assets[1] = IAsset(WNATIVE);
        
        //Only min we need to set is for the balance going in
        limits[0] = int(_amountIn);

        IERC20(ib).safeApprove(address(balancerVault), _amountIn);

        balancerVault.batchSwap(
            IBalancerVault.SwapKind.GIVEN_IN, 
            swaps, 
            assets, 
            _getFundManagement(), 
            limits, 
            block.timestamp
        );
    }

    function _getFundManagement() 
        internal 
        view 
        returns (IBalancerVault.FundManagement memory fundManagement) 
    {
        fundManagement = IBalancerVault.FundManagement(
                address(this),
                false,
                payable(address(this)),
                false
            );
    }

    function _getTokenOutPath(address _tokenIn, address _tokenOut) internal view returns (IVeledrome.route[] memory _path) {
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
        uint256 balance = balanceOfWant();
        require(cToken.mint(balance) == 0, "ctoken: mint fail");
        _stake();
    }

    function _stake() internal {
        uint256 balance = balanceOfCToken();
        if(address(stakingRewards) == address(0) || balance == 0) return;

        stakingRewards.stake(balance);
    }

    function _unStake(uint256 amount) internal {
        if(address(stakingRewards) == address(0) || amount == 0) return;

        stakingRewards.withdraw(Math.min(amount, stakedBalance()));
    }

    function manualUnstake(uint256 amount) external management {
        stakingRewards.withdraw(Math.min(amount, stakedBalance()));
    }

    function withdrawAll() external override management returns (bool) {
        //Call to accrue rewards and update exchange rate first
        cToken.accrueInterest();
        uint256 liquidity = want.balanceOf(address(cToken));
        uint256 liquidityInCTokens = _convertFromUnderlying(liquidity);
        _unStake(stakedBalance());
        uint256 amountInCtokens = balanceOfCToken();

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
                liquidityInCTokens = _convertFromUnderlying(want.balanceOf(address(cToken)));
                //take all we can
                all = false;
                cToken.redeem(liquidityInCTokens);
            }
        }

        uint256 looseBalance = balanceOfWant();
        if(looseBalance > 0){
            want.safeTransfer(address(strategy), looseBalance);
        }
        return all;

    }

    function _convertFromUnderlying(uint256 amountOfUnderlying) internal view returns (uint256 balance){
        if (amountOfUnderlying == 0) {
            balance = 0;
        } else {
            balance = amountOfUnderlying.mul(1e18).div(cToken.exchangeRateStored());
        }
    }

    function hasAssets() external view override returns (bool) {
        return underlyingBalanceStored() > 0 || balanceOfWant() > 0;
    }

    function aprAfterDeposit(uint256 amount) external view override returns (uint256) {
        uint256 cashPrior = want.balanceOf(address(cToken));

        uint256 borrows = cToken.totalBorrows();

        uint256 reserves = cToken.totalReserves();

        uint256 reserverFactor = cToken.reserveFactorMantissa();

        InterestRateModel model = cToken.interestRateModel();

        //the supply rate is derived from the borrow rate, reserve factor and the amount of total borrows.
        uint256 supplyRate = model.getSupplyRate(cashPrior.add(amount), borrows, reserves, reserverFactor);
        supplyRate = supplyRate.add(compBlockShareInWant(amount));

        return supplyRate.mul(blocksPerYear);
    }

    function protectedTokens() internal view override returns (address[] memory) {
        address[] memory protected = new address[](1);
        protected[0] = address(want);
        return protected;
    }

    // ---------------------- YSWAPS FUNCTIONS ----------------------
    function setTradeFactory(address _tradeFactory) external onlyGovernance {
        if (tradeFactory != address(0)) {
            _removeTradeFactoryPermissions();
        }

        ITradeFactory tf = ITradeFactory(_tradeFactory);

        IERC20(ib).safeApprove(_tradeFactory, type(uint256).max);
        tf.enable(ib, address(want));
        
        tradeFactory = _tradeFactory;
    }

    function removeTradeFactoryPermissions() external management {
        _removeTradeFactoryPermissions();
    }

    function _removeTradeFactoryPermissions() internal {
        IERC20(ib).safeApprove(tradeFactory, 0);
        
        tradeFactory = address(0);
    }

    modifier keepers() {
        require(
            msg.sender == address(keep3r) || msg.sender == address(strategy) || msg.sender == vault.governance() || msg.sender == IBaseStrategy(strategy).strategist(),
            "!keepers"
        );
        _;
    }
}