// SPDX-License-Identifier: GPL-3.0
pragma solidity >=0.6.12;
pragma experimental ABIEncoderV2;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/math/SafeMath.sol";
import "@openzeppelin/contracts/utils/Address.sol";
import "@openzeppelin/contracts/token/ERC20/SafeERC20.sol";

import "../Interfaces/UniswapInterfaces/IUniswapV2Router02.sol";

import "./GenericLenderBase.sol";
import {IAToken} from "../Interfaces/Aave/V3/IAtoken.sol";
import {IStakedAave} from "../Interfaces/Aave/V3/IStakedAave.sol";
import {IPool} from "../Interfaces/Aave/V3/IPool.sol";
import {IProtocolDataProvider} from "../Interfaces/Aave/V3/IProtocolDataProvider.sol";
import {IRewardsController} from "../Interfaces/Aave/V3/IRewardsController.sol";
import {DataTypesV3} from "../Libraries/Aave/V3/DataTypesV3.sol";
import {ITradeFactory} from "../Interfaces/ySwaps/ITradeFactory.sol";

interface IBaseFee {
    function isCurrentBaseFeeAcceptable() external view returns (bool);
}

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

/********************
 *   A lender plugin for LenderYieldOptimiser for any erc20 asset on AaveV3
 *   Made by SamPriestley.com & jmonteer. Updated for V3 by Schlagatron
 *   https://github.com/Grandthrax/yearnV2-generic-lender-strat/blob/master/contracts/GenericLender/GenericAave.sol
 *
 ********************* */

contract GenericSpark is GenericLenderBase {
    using SafeERC20 for IERC20;
    using Address for address;
    using SafeMath for uint256;

    IProtocolDataProvider public constant protocolDataProvider = IProtocolDataProvider(0xFc21d6d146E6086B8359705C8b28512a983db0cb);
    IAToken public aToken;
    
    // stkAave addresses only Applicable for Mainnet, We leave then since they wont be called on any other chain
    IStakedAave private constant stkAave = IStakedAave(0x4da27a545c0c5B758a6BA100e3a049001de870f5);
    address private constant AAVE = address(0x7Fc66500c84A76Ad7e9c93437bFc5Ac33E2DDaE9);

    address public keep3r;

    // to check if we should calculate reward apr
    bool public isIncentivised;
    //Amount to return true in harvestTrigger
    uint256 public minRewardsToHarvest;

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

    // Uni V2 routers we use for rewards and apr calculations
    address public baseRouter;
    address public secondRouter;
    //Uni v2 router to be used
    IUniswapV2Router02 public router;

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
        GenericSpark(newLender).initialize(WNATIVE, _baseRouter, _secondRouter, _isIncentivised);
    }

    function _initialize(
        address _wNative, 
        address _baseRouter, 
        address _secondRouter, 
        bool _isIncentivised
    ) internal {
        require(address(aToken) == address(0), "GenericAave already initialized");

        aToken = IAToken(_lendingPool().getReserveData(address(want)).aTokenAddress);

        // if incentivised get the applicable rewards controller
        if(_isIncentivised) {
            address rewardController = address(aToken.getIncentivesController());
            require(rewardController != address(0), "!aToken does not have incentives controller set up");
            isIncentivised = _isIncentivised;
        }

        IERC20(address(want)).safeApprove(address(_lendingPool()), type(uint256).max);

        //Set Chain Specific Addresses
        WNATIVE = _wNative;
        baseRouter = _baseRouter;
        secondRouter = _secondRouter;
        minRewardsToHarvest = 10e18;
        router = IUniswapV2Router02(_baseRouter);
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

    function changeRouter() external management {
        address currentRouter = address(router);

        router = currentRouter == baseRouter ? IUniswapV2Router02(secondRouter) : IUniswapV2Router02(baseRouter);
    }

    function setReferralCode(uint16 _customReferral) external management {
        require(_customReferral != 0, "!invalid referral code");
        customReferral = _customReferral;
    }

    function setKeep3r(address _keep3r) external management {
        keep3r = _keep3r;
    }

    function setMinRewardsToHarvest(uint256 _minRewardsToHarvest) external management {
        minRewardsToHarvest = _minRewardsToHarvest;
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

    // to be called by management if the trigger can not start a cooldown
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

    // calculates APR from Liquidity Mining Program for a specific reward token
    // kept public for debugging purposes
    function _incentivesRate(uint256 totalLiquidity, address rewardToken) public view returns (uint256) {
        // only returns != 0 if the incentives are in place at the moment.
        // Return 0 incase an improper address is sent so the whole tx doesnt fail
        if(rewardToken == address(0)) return 0;

        // make sure we should be calculating the apr and that the distro period hasnt ended
        if(isIncentivised && block.timestamp < _incentivesController().getDistributionEnd(address(aToken), rewardToken)) {
            uint256 _emissionsPerSecond;
            (, _emissionsPerSecond, , ) = _incentivesController().getRewardsData(address(aToken), rewardToken);
            if(_emissionsPerSecond > 0) {
                uint256 emissionsInWant;
                // we need to get the market rate from the reward token to want
                if(rewardToken == address(want)) {
                    // no calculation needed if rewarded in want
                    emissionsInWant = _emissionsPerSecond;
                } else if(rewardToken == address(stkAave)){
                    // if the reward token is stkAave we will be selling Aave
                    emissionsInWant = _checkPrice(AAVE, address(want), _emissionsPerSecond);
                } else {
                    // else just check the price
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
        // if we want to calculate the reward apr
        if(isIncentivised) {
            uint256 totalLiquidity = newLiquidity.add(unbacked).add(totalStableDebt).add(totalVariableDebt);

            // get all of the current reward tokens
            address[] memory rewardTokens = _incentivesController().getRewardsByAsset(address(aToken));
            uint256 i;
            uint256 tokenIncentivesRate;
            //Passes the total Supply and the corresponding reward token address for each reward token the want has
            while(i < rewardTokens.length && i < maxLoops) {
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

    // this is a manual trigger to claim rewards and sell them if tradeFactory is not set
    function harvest() external keepers{

        //Need to redeem any aave from StkAave first if applicable before claiming rewards and staring cool down over
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
                // if reward token is stkAave we need to start the cooldown process
                harvestStkAave();
            } else if(token == address(want)) {
                continue;   
            } else {
                // swap token if trade factory isnt set
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
        // can only redeem if the cooldown period if over
        if(!_checkCooldown()) {
            return;
        }

        uint256 stkAaveBalance = IERC20(address(stkAave)).balanceOf(address(this));
        if(stkAaveBalance > 0) {
            // if we have a stkAave balance redeem it for AAVE
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
        address[] memory assets = new address[](1);
        assets[0] = address(aToken);

        //check the total rewards available
        (address[] memory tokens, uint256[] memory rewards) = 
            _incentivesController().getAllUserRewards(assets, address(this));

        // we will add up all the rewards we are owed in terms of wnative
        uint256 expectedRewards = 0;
        // If we have a positive amount of any rewards return true
        for(uint256 i = 0; i < rewards.length; i ++) {

            address token = tokens[i];
            if(token == WNATIVE){
                // if already in wnative we dont need to do anything
                expectedRewards += rewards[i];
            } else if(token == address(stkAave)) {
                // if stkAave is a reward token we should only be harvesting after the cooldown
                if(!_checkCooldown()) return false;
                // account for both pending and claimed stkAave
                expectedRewards += _checkPrice(AAVE, WNATIVE, rewards[i] + IERC20(address(stkAave)).balanceOf(address(this)));
            } else {
                expectedRewards += _checkPrice(token, WNATIVE, rewards[i]);
            }
        }
        
        // return true if rewards are over the amount and base fee is low enough
        if(expectedRewards >= minRewardsToHarvest) {
            return isBaseFeeAcceptable();
        }
    }

    // check if the current baseFee is below our external target
    function isBaseFeeAcceptable() internal view returns (bool) {
        return
            IBaseFee(0xb5e1CAcB567d98faaDB60a1fD4820720141f064F)
                .isCurrentBaseFeeAcceptable();
    }

    function _nav() internal view returns (uint256) {
        return want.balanceOf(address(this)).add(underlyingBalanceStored());
    }

    function _apr() internal view returns (uint256) {
        uint256 liquidityRate = uint256(_lendingPool().getReserveData(address(want)).currentLiquidityRate).div(1e9);// dividing by 1e9 to pass from ray to wad

        uint256 incentivesRate;
        // only check rewads if the token is incentivised
        if(isIncentivised) {
            (uint256 unbacked, , , uint256 totalStableDebt, uint256 totalVariableDebt, , , , , , , ) =
                protocolDataProvider.getReserveData(address(want));

            uint256 availableLiquidity = want.balanceOf(address(aToken));

            // get the full amount of assets that are earning interest
            uint256 totalLiquidity = availableLiquidity.add(unbacked).add(totalStableDebt).add(totalVariableDebt);

            // get all the reward tokens being earned
            address[] memory rewardTokens = _incentivesController().getRewardsByAsset(address(aToken));
            uint256 i;
            uint256 tokenIncentivesRate;
            //Passes the total Supply and the corresponding reward token address for each reward token the want has
            while(i < rewardTokens.length && i < maxLoops) {
           
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

    // function to check if the cooldown has ended and stkAave can be claimed
    function _checkCooldown() internal view returns (bool) {
        // only checks the cooldown if we are on mainnet eth
        uint256 id;
        assembly {
            id := chainid()
        }
        if(id != 1) {
            return false;
        }
        // whem we started the last cooldown
        uint256 cooldownStartTimestamp = IStakedAave(stkAave).stakersCooldowns(address(this));
        // if we never started a cooldown there is nothing to redeem
        if(cooldownStartTimestamp == 0) return false;
        // how long it needs to wait
        uint256 COOLDOWN_SECONDS = IStakedAave(stkAave).COOLDOWN_SECONDS();
        // the time period we have to claim once cooldown is over
        uint256 UNSTAKE_WINDOW = IStakedAave(stkAave).UNSTAKE_WINDOW();

        // if we have waited the full cooldown period
        if(block.timestamp >= cooldownStartTimestamp.add(COOLDOWN_SECONDS)) {
            // only return true if the period hasnt expired
            return block.timestamp.sub(cooldownStartTimestamp.add(COOLDOWN_SECONDS)) <= UNSTAKE_WINDOW;
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
        // dont swap if the tradeFactory is set
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

    function getTokenOutPath(address _tokenIn, address _tokenOut) internal view returns (address[] memory _path) {
        bool isNative = _tokenIn == WNATIVE || _tokenOut == WNATIVE;
        _path = new address[](isNative ? 2 : 3);
        _path[0] = _tokenIn;

        if (isNative) {
            _path[1] = _tokenOut;
        } else {
            _path[1] = WNATIVE;
            _path[2] = _tokenOut;
        }
    }

    function _lendingPool() internal view returns (IPool lendingPool) {
        lendingPool = IPool(protocolDataProvider.ADDRESSES_PROVIDER().getPool());
    }

    function _incentivesController() internal view returns (IRewardsController) {
        return aToken.getIncentivesController();
    }

    function protectedTokens() internal view override returns (address[] memory) {
        address[] memory protected = new address[](2);
        protected[0] = address(want);
        protected[1] = address(aToken);
        return protected;
    }

    modifier keepers() {
        require(
            msg.sender == address(keep3r) || msg.sender == address(strategy) || msg.sender == vault.governance() || msg.sender == vault.management(),
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
                    // if stkAave is the reward Aave is what the trade factory should be swapping
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
                    // if stkAave is the reward Aave is what the trade factory should be swapping
                    IERC20(AAVE).safeApprove(tradeFactory, 0);
                    ITradeFactory(tradeFactory).disable(AAVE, address(want));
                } else {
                    IERC20(token).safeApprove(tradeFactory, 0);
                    ITradeFactory(tradeFactory).disable(token, address(want));
                }
            }
        }
        tradeFactory = address(0);
    }
}
