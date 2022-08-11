// SPDX-License-Identifier: GPL-3.0
pragma solidity >=0.6.12;
pragma experimental ABIEncoderV2;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/math/SafeMath.sol";
import "@openzeppelin/contracts/utils/Address.sol";
import "@openzeppelin/contracts/token/ERC20/SafeERC20.sol";

import "../Interfaces/UniswapInterfaces/IUniswapV2Router02.sol";

import "./GenericLenderBase.sol";
import {IAToken} from "../Interfaces/Aave/V3/IAToken.sol";
import {IStakedAave} from "../Interfaces/Aave/V3/IStakedAave.sol";
import {IPool} from "../Interfaces/Aave/V3/IPool.sol";
import {IProtocolDataProvider} from "../Interfaces/Aave/V3/IProtocolDataProvider.sol";
import {IRewardsController} from "../Interfaces/Aave/V3/IRewardsController.sol";
import {DataTypesV3} from "../Libraries/Aave/V3/DataTypesV3.sol";
import {ITradeFactory} from "../Interfaces/ySwap/ITradeFactory.sol";

//-- IReserveInterestRateStrategy implemented manually to avoid compiler errors for aprAfterDeposit function --//
/**
 * @title IReserveInterestRateStrategy
 * @author Aave
 * @notice Interface for the calculation of the interest rates
 */
interface IReserveInterestRateStrategy {
  /**
   * @notice Calculates the interest rates depending on the reserve's state and configurations
   * @param params The parameters needed to calculate interest rates
   * @return liquidityRate The liquidity rate expressed in rays
   * @return stableBorrowRate The stable borrow rate expressed in rays
   * @return variableBorrowRate The variable borrow rate expressed in rays
   **/
  function calculateInterestRates(DataTypesV3.CalculateInterestRatesParams calldata params)
    external
    view
    returns (
      uint256,
      uint256,
      uint256
    );
}

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

/********************
 *   A lender plugin for LenderYieldOptimiser for any erc20 asset on AaveV3
 *   Made by SamPriestley.com & jmonteer. Updated for V3 by Schlagatron
 *   https://github.com/Grandthrax/yearnV2-generic-lender-strat/blob/master/contracts/GenericLender/GenericAave.sol
 *
 ********************* */

contract GenericAaveV3 is GenericLenderBase {
    using SafeERC20 for IERC20;
    using Address for address;
    using SafeMath for uint256;

    //Should be the same for all EVM chains
    IProtocolDataProvider public constant protocolDataProvider = IProtocolDataProvider(address(0x69FA688f1Dc47d4B5d8029D5a35FB7a548310654));
    IAToken public aToken;
    
    //Only Applicable for Mainnet, We leave then since they wont be called on any other chain
    IStakedAave private constant stkAave = IStakedAave(0x4da27a545c0c5B758a6BA100e3a049001de870f5);
    address private constant AAVE = address(0x7Fc66500c84A76Ad7e9c93437bFc5Ac33E2DDaE9);

    address public keep3r;

    bool public isIncentivised;
    //Amount to multiply callcost by in harvestTrigger
    uint256 profitFactor;

    // Used to assure we stop infinite while loops
    //Should never be more reward tokens than 5
    uint256 public constant maxLoops = 5;

    uint16 internal constant DEFAULT_REFERRAL = 7; 
    uint16 internal customReferral;

    /*** 
    Chain specific addresses that will be set on Constructor
    ***/
    //Wrapped native token for chain i.e. WETH
    address public WNATIVE;
    //USDC for the middle of swaps
    address internal constant usdc = 0x7F5c764cBc14f9669B88837ca1490cCa17c31607;
    //Asset to use for swap as the middle
    address public middleSwapToken;
    //stable bool should be true if we are using usdc as the middle token and want is a stable coin
    bool public stable;
    ///For Optimism we will only be using the Veledrome router \\\\
    address public baseRouter;
    address public secondRouter;
    //Uni v2 router to be used
    IVeledrome public router;

    address public tradeFactory;

    uint256 constant internal SECONDS_IN_YEAR = 365 days;

    /// @param _strategy The strategy that will connect the lender to
    /// @param _wNative The wrapped native token for chain. i.e. WETH/WFTM
    /// @param _baseRouter Address of a UniV2 Router to be used
    /// @param _secondRouter Address of the second router to be used as a backup
    /// @param name The name of the Strategy
    /// @param _isIncentivised Bool repersenting wether or not the pool has reward tokens currently
    constructor(
        address _strategy,
        address _wNative,
        address _baseRouter,
        address _secondRouter,
        string memory name,
        bool _isIncentivised
    ) public GenericLenderBase(_strategy, name) {
        _initialize(_wNative, _baseRouter, _secondRouter, _isIncentivised);
    }

    function initialize(
        address _wNative,
        address _baseRouter,
        address _secondRouter,
        bool _isIncentivised
    ) external {
        _initialize(_wNative, _baseRouter, _secondRouter, _isIncentivised);
    }

    function cloneAaveLender(
        address _strategy,
        address _baseRouter,
        address _secondRouter,
        string memory _name,
        bool _isIncentivised
    ) external returns (address newLender) {
        newLender = _clone(_strategy, _name);
        GenericAaveV3(newLender).initialize(WNATIVE, _baseRouter, _secondRouter, _isIncentivised);
    }

    function _initialize(
        address _wNative, 
        address _baseRouter, 
        address _secondRouter, 
        bool _isIncentivised
    ) internal {
        require(address(aToken) == address(0), "GenericAave already initialized");

        aToken = IAToken(_lendingPool().getReserveData(address(want)).aTokenAddress);

        if(_isIncentivised) {
            address rewardController = address(aToken.getIncentivesController());
            require(rewardController != address(0), "!aToken does not have incentives controller set up");
        }
        isIncentivised = _isIncentivised;

        IERC20(address(want)).safeApprove(address(_lendingPool()), type(uint256).max);

        //Defaul to USDC due to Veledrome liquidity
        middleSwapToken = usdc;
    
        //Set Chain Specific Addresses
        WNATIVE = _wNative;
        baseRouter = _baseRouter;
        secondRouter = _secondRouter;
        profitFactor = 100;
        router = IVeledrome(_baseRouter);
    }

    // for the management to activate / deactivate incentives functionality
    function setIsIncentivised(bool _isIncentivised) external management {
        // NOTE: if the aToken is not incentivised, getIncentivesController() might revert (aToken won't implement it)
        // to avoid calling it, we use the if else statement to check for valid address
        if(_isIncentivised) {
            address rewardController = address(aToken.getIncentivesController());
            require(rewardController != address(0), "!aToken does not have incentives controller set up");
        } 
        isIncentivised = _isIncentivised;
    }

    //On optimism there is only one router that complies with the Teledrome interfaces so this will not apply
    function changeRouter() external management {
        address currentRouter = address(router);

        router = currentRouter == baseRouter ? IVeledrome(secondRouter) : IVeledrome(baseRouter);
    }

    function setReferralCode(uint16 _customReferral) external management {
        require(_customReferral != 0, "!invalid referral code");
        customReferral = _customReferral;
    }

    function setProfitFactor(uint256 _profitFactor) external management {
        profitFactor = _profitFactor;
    }

    function setKeep3r(address _keep3r) external management {
        keep3r = _keep3r;
    }

    function deposit() external override management {
        uint256 balance = want.balanceOf(address(this));
        _deposit(balance);
    }

    function withdraw(uint256 amount) external override management returns (uint256) {
        return _withdraw(amount);
    }

    //emergency withdraw. sends balance plus amount to governance
    function emergencyWithdraw(uint256 amount) external override onlyGovernance {
        _lendingPool().withdraw(address(want), amount, address(this));

        want.safeTransfer(vault.governance(), want.balanceOf(address(this)));
    }

    function withdrawAll() external override management returns (bool) {
        uint256 invested = _nav();
        uint256 returned = _withdraw(invested);
        return returned >= invested;
    }

    function startCooldown() external management {
        // for emergency cases
        IStakedAave(stkAave).cooldown(); // it will revert if balance of stkAave == 0
    }

    function nav() external view override returns (uint256) {
        return _nav();
    }

    function underlyingBalanceStored() public view returns (uint256 balance) {
        balance = aToken.balanceOf(address(this));
    }

    function apr() external view override returns (uint256) {
        return _apr();
    }

    function weightedApr() external view override returns (uint256) {
        uint256 a = _apr();
        return a.mul(_nav());
    }

    // calculates APR from Liquidity Mining Program
    function _incentivesRate(uint256 totalLiquidity, address rewardToken) public view returns (uint256) {
        // only returns != 0 if the incentives are in place at the moment.
        // Return 0 incase an improper address is sent so the whole tx doesnt fail
        if(rewardToken == address(0)) return 0;

        if(isIncentivised && block.timestamp < _incentivesController().getDistributionEnd(address(aToken), rewardToken)) {
            uint256 _emissionsPerSecond;
            (, _emissionsPerSecond, , ) = _incentivesController().getRewardsData(address(aToken), rewardToken);
            if(_emissionsPerSecond > 0) {
                uint256 emissionsInWant;
                if(rewardToken == address(want)) {
                    emissionsInWant = _emissionsPerSecond;
                } else if(rewardToken == address(stkAave)){
                    emissionsInWant = _checkPrice(AAVE, address(want), _emissionsPerSecond);
                } else {
                    emissionsInWant = _checkPrice(rewardToken, address(want), _emissionsPerSecond); // amount of emissions in want
                }

                uint256 incentivesRate = emissionsInWant.mul(SECONDS_IN_YEAR).mul(1e18).div(totalLiquidity); // APRs are in 1e18

                return incentivesRate.mul(9_500).div(10_000); // 95% of estimated APR to avoid overestimations
            }
        }
        return 0;
    }

    function aprAfterDeposit(uint256 extraAmount) external view override returns (uint256) {
        //need to calculate new supplyRate after Deposit (when deposit has not been done yet)
        DataTypesV3.ReserveData memory reserveData = _lendingPool().getReserveData(address(want));

        (uint256 unbacked, , , uint256 totalStableDebt, uint256 totalVariableDebt, , , , uint256 averageStableBorrowRate, , , ) =
            protocolDataProvider.getReserveData(address(want));

        uint256 availableLiquidity = want.balanceOf(address(aToken));

        uint256 newLiquidity = availableLiquidity.add(extraAmount);

        uint256 totalLiquidity = newLiquidity.add(unbacked).add(totalStableDebt).add(totalVariableDebt);

        (, , , , uint256 reserveFactor, , , , , ) = protocolDataProvider.getReserveConfigurationData(address(want));

        DataTypesV3.CalculateInterestRatesParams memory params = DataTypesV3.CalculateInterestRatesParams(
            unbacked,
            extraAmount,
            0,
            totalStableDebt,
            totalVariableDebt,
            averageStableBorrowRate,
            reserveFactor,
            address(want),
            address(aToken)
        );

        (uint256 newLiquidityRate, , ) = IReserveInterestRateStrategy(reserveData.interestRateStrategyAddress).calculateInterestRates(params);

        uint256 incentivesRate = 0;
        if(isIncentivised) {

            address[] memory rewardTokens = _incentivesController().getRewardsByAsset(address(aToken));
            uint256 i = 0;
            uint256 _maxLoops = maxLoops;
            uint256 tokenIncentivesRate;
            //Passes the total Supply and the corresponding reward token address for each reward token the want has
            while(i < rewardTokens.length && i < _maxLoops) {
                tokenIncentivesRate = _incentivesRate(totalLiquidity, rewardTokens[i]); 

                incentivesRate += tokenIncentivesRate;

                i ++;
            }
        }

        return newLiquidityRate.div(1e9).add(incentivesRate); // divided by 1e9 to go from Ray to Wad
    }

    function hasAssets() external view override returns (bool) {
        return aToken.balanceOf(address(this)) > dust || want.balanceOf(address(this)) > dust;
    }

    // Only for incentivised aTokens
    // this is a manual trigger to claim rewards
    // only callable if the token is incentivised by Aave Governance
    function harvest() external keepers{
        require(isIncentivised, "Not incevtivised, Nothing to harvest");

        //Need to redeem and aave from StkAave if applicable before claiming rewards and staring cool down over
        redeemAave();

        //claim all rewards
        address[] memory assets = new address[](1);
        assets[0] = address(aToken);
        (address[] memory rewardsList, uint256[] memory claimedAmounts) = 
            _incentivesController().claimAllRewardsToSelf(assets);
        
        //swap as much as possible back to want
        address token;
        for(uint256 i = 0; i < rewardsList.length; i ++) {
            token = rewardsList[i];

            if(token == address(stkAave)) {
                harvestStkAave();
            } else if(token == address(want)) {
                continue;   
            } else {
                _swapFrom(token, address(want), IERC20(token).balanceOf(address(this)));
            }
        }

        // deposit want in lending protocol
        uint256 balance = want.balanceOf(address(this));
        if(balance > 0) {
            _deposit(balance);
        }
    }

    function redeemAave() internal {
        if(!_checkCooldown()) {
            return;
        }

        uint256 stkAaveBalance = IERC20(address(stkAave)).balanceOf(address(this));
        if(stkAaveBalance > 0) {
            stkAave.redeem(address(this), stkAaveBalance);
        }

        // sell AAVE for want
        _swapFrom(AAVE, address(want), IERC20(AAVE).balanceOf(address(this)));

    }

    function harvestStkAave() internal {
        // request start of cooldown period
        if(IERC20(address(stkAave)).balanceOf(address(this)) > 0) {
            stkAave.cooldown();
        }
    }

    function harvestTrigger(uint256 callcost) external view returns (bool) {
        if(!isIncentivised) {
            return false;
        }

        address[] memory assets = new address[](1);
        assets[0] = address(aToken);

        //check the total rewards available
        (address[] memory tokens, uint256[] memory rewards) = 
            _incentivesController().getAllUserRewards(assets, address(this));

        uint256 expectedRewards = 0;
        // If we have a positive amount of any rewards return true
        for(uint256 i = 0; i < rewards.length; i ++) {

            address token = tokens[i];
            if(token == WNATIVE){
                expectedRewards += rewards[i];
            } else if(token == address(stkAave)) {
                expectedRewards += _checkPrice(AAVE, WNATIVE, rewards[i]);
            } else {
                expectedRewards += _checkPrice(token, WNATIVE, rewards[i]);
            }
        }
        
        return expectedRewards >= callcost.mul(profitFactor);
    }

    function _nav() internal view returns (uint256) {
        return want.balanceOf(address(this)).add(underlyingBalanceStored());
    }

    function _apr() internal view returns (uint256) {
        uint256 liquidityRate = uint256(_lendingPool().getReserveData(address(want)).currentLiquidityRate).div(1e9);// dividing by 1e9 to pass from ray to wad

        (uint256 unbacked, , , uint256 totalStableDebt, uint256 totalVariableDebt, , , , , , , ) =
            protocolDataProvider.getReserveData(address(want));

        uint256 availableLiquidity = want.balanceOf(address(aToken));

        uint256 totalLiquidity = availableLiquidity.add(unbacked).add(totalStableDebt).add(totalVariableDebt);

        uint256 incentivesRate = 0;
        if(isIncentivised) {

            address[] memory rewardTokens = _incentivesController().getRewardsByAsset(address(aToken));
            uint256 i = 0;
            uint256 _maxLoops = maxLoops;
            uint256 tokenIncentivesRate;
            //Passes the total Supply and the corresponding reward token address for each reward token the want has
            while(i < rewardTokens.length && i < _maxLoops) {
                tokenIncentivesRate = _incentivesRate(totalLiquidity, rewardTokens[i]); 

                incentivesRate += tokenIncentivesRate;

                i ++;
            }
        }
        return liquidityRate.add(incentivesRate);
    }

    //withdraw an amount including any want balance
    function _withdraw(uint256 amount) internal returns (uint256) {
        uint256 balanceUnderlying = underlyingBalanceStored();
        uint256 looseBalance = want.balanceOf(address(this));
        uint256 total = balanceUnderlying.add(looseBalance);

        if (amount > total) {
            //cant withdraw more than we own
            amount = total;
        }

        if (looseBalance >= amount) {
            want.safeTransfer(address(strategy), amount);
            return amount;
        }

        //not state changing but OK because of previous call
        uint256 liquidity = want.balanceOf(address(aToken));

        if (liquidity > dust) {
            uint256 toWithdraw = amount.sub(looseBalance);

            if (toWithdraw <= liquidity) {
                //we can take all
                _lendingPool().withdraw(address(want), toWithdraw, address(this));
            } else {
                //take all we can
                _lendingPool().withdraw(address(want), liquidity, address(this));
            }
        }
        looseBalance = want.balanceOf(address(this));
        want.safeTransfer(address(strategy), looseBalance);
        return looseBalance;
    }

    function _deposit(uint256 amount) internal {
        IPool lp = _lendingPool();
        // NOTE: check if allowance is enough and acts accordingly
        // allowance might not be enough if
        //     i) initial allowance has been used (should take years)
        //     ii) lendingPool contract address has changed (Aave updated the contract address)
        if(want.allowance(address(this), address(lp)) < amount){
            IERC20(address(want)).safeApprove(address(lp), 0);
            IERC20(address(want)).safeApprove(address(lp), type(uint256).max);
        }

        uint16 referral;
        uint16 _customReferral = customReferral;
        if(_customReferral != 0) {
            referral = _customReferral;
        } else {
            referral = DEFAULT_REFERRAL;
        }

        lp.supply(address(want), amount, address(this), referral);
    }

    function _checkCooldown() internal view returns (bool) {
        uint256 id;
        assembly {
            id := chainid()
        }
        if(id != 1) {
            return false;
        }

        uint256 cooldownStartTimestamp = IStakedAave(stkAave).stakersCooldowns(address(this));
        uint256 COOLDOWN_SECONDS = IStakedAave(stkAave).COOLDOWN_SECONDS();
        uint256 UNSTAKE_WINDOW = IStakedAave(stkAave).UNSTAKE_WINDOW();
        if(block.timestamp >= cooldownStartTimestamp.add(COOLDOWN_SECONDS)) {
            return block.timestamp.sub(cooldownStartTimestamp.add(COOLDOWN_SECONDS)) <= UNSTAKE_WINDOW || cooldownStartTimestamp == 0;
        } else {
            return false;
        }
    }

    function _checkPrice(
        address start,
        address end,
        uint256 _amount
    ) internal view returns (uint256) {
        if (_amount == 0) {
            return 0;
        }

        uint256[] memory amounts = router.getAmountsOut(_amount, getTokenOutPath(start, end));

        return amounts[amounts.length - 1];
    }

    function _swapFrom(address _from, address _to, uint256 _amountIn) internal{
        if (_amountIn == 0 || tradeFactory != address(0)) {
            return;
        }

        if(IERC20(_from).allowance(address(this), address(router)) < _amountIn) {
            IERC20(_from).safeApprove(address(router), 0);
            IERC20(_from).safeApprove(address(router), type(uint256).max);
        }

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

    function _lendingPool() internal view returns (IPool lendingPool) {
        lendingPool = IPool(protocolDataProvider.ADDRESSES_PROVIDER().getPool());
    }

    function _incentivesController() internal view returns (IRewardsController) {
        if(isIncentivised) {
            return aToken.getIncentivesController();
        } else {
            return IRewardsController(0);
        }
    }

    function protectedTokens() internal view override returns (address[] memory) {
        address[] memory protected = new address[](2);
        protected[0] = address(want);
        protected[1] = address(aToken);
        return protected;
    }

    modifier keepers() {
        require(
            msg.sender == address(keep3r) || msg.sender == address(strategy) || msg.sender == vault.governance() || msg.sender == IBaseStrategy(strategy).management(),
            "!keepers"
        );
        _;
    }

    // ---------------------- YSWAPS FUNCTIONS ----------------------
    function setTradeFactory(address _tradeFactory) external onlyGovernance {
        if (tradeFactory != address(0)) {
            _removeTradeFactoryPermissions();
        }

        if(isIncentivised) {
            address[] memory rewardTokens = _incentivesController().getRewardsByAsset(address(aToken));
            ITradeFactory tf = ITradeFactory(_tradeFactory);
            for(uint256 i; i < rewardTokens.length; i ++) {
                address token = rewardTokens[i];
                if(token == address(stkAave)) {
                    IERC20(AAVE).safeApprove(_tradeFactory, type(uint256).max);

                    tf.enable(AAVE, address(want));
                } else if (token == address(want)) {
                    continue;
                } else {
                    IERC20(token).safeApprove(_tradeFactory, type(uint256).max);

                    tf.enable(token, address(want));
                }
            }
        }
        tradeFactory = _tradeFactory;
    }

    function removeTradeFactoryPermissions() external management {
        _removeTradeFactoryPermissions();
    }

    function _removeTradeFactoryPermissions() internal {
        if(isIncentivised) {
            address[] memory rewardTokens = _incentivesController().getRewardsByAsset(address(aToken));
            for(uint256 i; i < rewardTokens.length; i ++) {
                address token = rewardTokens[i];
                if(token == address(stkAave)) {
                    IERC20(AAVE).safeApprove(tradeFactory, 0);
                } else {
                    IERC20(token).safeApprove(tradeFactory, 0);
                }
            }
        }
        tradeFactory = address(0);
    }
}
