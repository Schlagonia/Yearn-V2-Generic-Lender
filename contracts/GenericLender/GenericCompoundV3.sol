// SPDX-License-Identifier: GPL-3.0
pragma solidity >=0.6.12;
pragma experimental ABIEncoderV2;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/math/SafeMath.sol";
import "@openzeppelin/contracts/utils/Address.sol";
import "@openzeppelin/contracts/token/ERC20/SafeERC20.sol";

import {CometStructs} from "../Interfaces/Compound/V3/CompoundV3.sol";
import {Comet} from "../Interfaces/Compound/V3/CompoundV3.sol";
import {CometRewards} from "../Interfaces/Compound/V3/CompoundV3.sol";
import {ITradeFactory} from "../Interfaces/ySwaps/ITradeFactory.sol";
import {ISwapRouter} from "../Interfaces/UniswapInterfaces/V3/ISwapRouter.sol";

import "./GenericLenderBase.sol";

/********************
 *   A lender plugin for LenderYieldOptimiser for any borrowable erc20 asset on compoundV3 (not eth)
 *   Made by @Schlagonia
 *   https://github.com/Schlagonia/Yearn-V2-Generic-Lender/blob/main/contracts/GenericLender/GenericCompoundV3.sol
 *
 ********************* */

interface IBaseFee {
    function isCurrentBaseFeeAcceptable() external view returns (bool);
}

contract GenericCompoundV3 is GenericLenderBase {
    using SafeERC20 for IERC20;
    using Address for address;
    using SafeMath for uint256;

    //For apr calculations
    uint internal constant DAYS_PER_YEAR = 365;
    uint internal constant SECONDS_PER_DAY = 60 * 60 * 24;
    uint internal constant SECONDS_PER_YEAR = 365 days;

    //Rewards stuff
    // Uniswap v3 router
    ISwapRouter internal constant router =
        ISwapRouter(0xE592427A0AEce92De3Edee1F18E0157C05861564);
    //Fees for the V3 pools if the supply is incentivized
    uint24 public compToEthFee;
    uint24 public ethToWantFee;
    address public constant comp = 
        0xc00e94Cb662C3520282E6f5717214004A7f26888;
    address public constant weth = 
        0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2;
    address public tradeFactory;

    Comet public comet;
    CometRewards public constant rewardsContract = 
        CometRewards(0x1B0e765F6224C21223AeA2af16c1C46E38885a40); 

    uint public BASE_MANTISSA;
    uint public BASE_INDEX_SCALE;

    uint256 public minCompToSell;
    uint256 public minRewardToHarvest;
    address public keep3r;

    constructor(
        address _strategy,
        string memory name,
        address _comet
    ) public GenericLenderBase(_strategy, name) {
        _initialize(_comet);
    }

    function initialize(address _comet) external {
        _initialize(_comet);
    }

    function _initialize(address _comet) internal {
        require(address(comet) == address(0), "already initialized");
        comet = Comet(_comet);
        require(comet.baseToken() == address(want), "wrong token");
        
        BASE_MANTISSA = comet.baseScale();
        BASE_INDEX_SCALE = comet.baseIndexScale();

        want.safeApprove(_comet, type(uint256).max);
        IERC20(comp).safeApprove(address(router), type(uint256).max);

        minCompToSell = 0.05 ether;
        minRewardToHarvest = 10 ether;
    }

    function cloneCompoundV3Lender(
        address _strategy,
        string memory _name,
        address _comet
    ) external returns (address newLender) {
        newLender = _clone(_strategy, _name);
        GenericCompoundV3(newLender).initialize(_comet);
    }

    function setRewardStuff(uint256 _minCompToSell, uint256 _minRewardToHavest) external management {
        minCompToSell = _minCompToSell;
        minRewardToHarvest = _minRewardToHavest;
    }

    //These will default to 0.
    //Will need to be manually set if want is incentized before any harvests
    function setUniFees(uint24 _compToEth, uint24 _ethToWant) external management {
        compToEthFee = _compToEth;
        ethToWantFee = _ethToWant;
    }

    function setKeep3r(address _keep3r) external management {
        keep3r = _keep3r;
    }

    function nav() external view override returns (uint256) {
        return _nav();
    }

    function _nav() internal view returns (uint256) {
        return want.balanceOf(address(this)).add(underlyingBalanceStored());
    }

    function underlyingBalanceStored() public view returns (uint256) {
        return comet.balanceOf(address(this));
    }

    function apr() external view override returns (uint256) {
        return _apr();
    }

    function _apr() internal view returns (uint256) {
        uint utilization = comet.getUtilization();
        uint supplyRate = comet.getSupplyRate(utilization) * SECONDS_PER_YEAR;
        uint rewardRate = getRewardAprForSupplyBase(getPriceFeedAddress(comp), 0);
        return uint256(supplyRate.add(rewardRate));
    }

    /*
    * Get the current reward for supplying APR in Compound III
    * @param rewardTokenPriceFeed The address of the reward token (e.g. COMP) price feed
    * @param newAmount Any amount that will be added to the total supply in a deposit
    * @return The reward APR in USD as a decimal scaled up by 1e18
    */
    function getRewardAprForSupplyBase(address rewardTokenPriceFeed, uint newAmount) public view returns (uint) {
        uint rewardTokenPriceInUsd = getCompoundPrice(rewardTokenPriceFeed);
        uint wantPriceInUsd = getCompoundPrice(comet.baseTokenPriceFeed());
        uint wantTotalSupply = comet.totalSupply().add(newAmount);
        uint baseTrackingSupplySpeed = comet.baseTrackingSupplySpeed();
        uint rewardToSuppliersPerDay = baseTrackingSupplySpeed * SECONDS_PER_DAY * (BASE_INDEX_SCALE / BASE_MANTISSA);
        uint supplyBaseRewardApr = (rewardTokenPriceInUsd * rewardToSuppliersPerDay / (wantTotalSupply * wantPriceInUsd)) * DAYS_PER_YEAR;
        return supplyBaseRewardApr;
    }

    function getPriceFeedAddress(address asset) public view returns (address) {
        return comet.getAssetInfoByAddress(asset).priceFeed;
    }

    function getCompoundPrice(address singleAssetPriceFeed) public view returns (uint) {
        return comet.getPrice(singleAssetPriceFeed);
    }

    function weightedApr() external view override returns (uint256) {
        uint256 a = _apr();
        return a.mul(_nav());
    }

    function withdraw(uint256 amount) external override management returns (uint256) {
        return _withdraw(amount);
    }

    //emergency withdraw. sends balance plus amount to governance
    function emergencyWithdraw(uint256 amount) external override onlyGovernance {
        //dont care about errors here. we want to exit what we can
        comet.withdraw(address(want), amount);

        want.safeTransfer(vault.governance(), want.balanceOf(address(this)));
    }

    //withdraw an amount including any want balance
    function _withdraw(uint256 amount) internal returns (uint256) { 
        //Accrue rewards and interest to the lender
        comet.accrueAccount(address(this));
        uint256 balanceUnderlying = comet.balanceOf(address(this));
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

        uint256 liquidity = comet.totalSupply().sub(comet.totalBorrow());

        if (liquidity > 1) {
            uint256 toWithdraw = amount.sub(looseBalance);

            if (toWithdraw <= liquidity) {
                //we can take all
                comet.withdraw(address(want), toWithdraw);
            } else {
                //take all we can
                comet.withdraw(address(want), liquidity);
            }
        }
        looseBalance = want.balanceOf(address(this));
        want.safeTransfer(address(strategy), looseBalance);
        return looseBalance;
    }

    function harvest() external keepers {
        claimCometRewards();

        _disposeOfComp();

        uint256 wantBalance = want.balanceOf(address(this));
        if(wantBalance > 0) {
            comet.supply(address(want), wantBalance);
        }
    }

    function harvestTrigger(uint256 /*callCost*/) external view returns(bool) {
        if(!isBaseFeeAcceptable()) return false;

        if(getRewardsOwed().add(IERC20(comp).balanceOf(address(this))) >= minRewardToHarvest) return true;
    }
    
    /*
    * Gets the amount of reward tokens due to this contract address
    */
    function getRewardsOwed() public view returns (uint) {
        return comet.userBasic(address(this)).baseTrackingAccrued;
    }

    /*
    * Claims the reward tokens due to this contract address
    */
    function claimCometRewards() internal {
        rewardsContract.claim(address(comet), address(this), true);
    }

    function _disposeOfComp() internal {
        //check for Trade Factory implementation or that Uni fees are not set
        if(tradeFactory != address(0) || ethToWantFee == 0) return;

        uint256 _comp = IERC20(comp).balanceOf(address(this));

        if (_comp > minCompToSell) {

            if(address(want) == weth) {
                ISwapRouter.ExactInputSingleParams memory params =
                    ISwapRouter.ExactInputSingleParams(
                        comp, // tokenIn
                        address(want), // tokenOut
                        compToEthFee, // comp-eth fee
                        address(this), // recipient
                        now, // deadline
                        _comp, // amountIn
                        0, // amountOut
                        0 // sqrtPriceLimitX96
                    );

                router.exactInputSingle(params);
            
            } else {
                bytes memory path =
                    abi.encodePacked(
                        comp, // comp-ETH
                        compToEthFee,
                        weth, // ETH-want
                        ethToWantFee,
                        address(want)
                    );

                // Proceeds from Comp are not subject to minExpectedSwapPercentage
                // so they could get sandwiched if we end up in an uncle block
                router.exactInput(
                    ISwapRouter.ExactInputParams(
                        path,
                        address(this),
                        now,
                        _comp,
                        0
                    )
                );
            }
        }
    }

    function deposit() external override management {
        uint256 balance = want.balanceOf(address(this));
        comet.supply(address(want), balance);
    }

    function withdrawAll() external override management returns (bool) {
        uint256 invested = _nav();
        uint256 returned = _withdraw(invested);
        return returned >= invested;
    }

    function hasAssets() external view override returns (bool) {
        return comet.balanceOf(address(this)) > 0 || want.balanceOf(address(this)) > 0;
    }

    function aprAfterDeposit(uint256 amount) external view override returns (uint256) {
        uint256 borrows = comet.totalBorrow();
        uint256 supply = comet.totalSupply();

        uint256 newUtilization = borrows.mul(1e18).div(supply.add(amount));
        uint256 newSupply = comet.getSupplyRate(newUtilization) * SECONDS_PER_YEAR;

        uint256 newReward = getRewardAprForSupplyBase(getPriceFeedAddress(comp), amount);
        return newSupply.add(newReward);
    }

    function protectedTokens() internal view override returns (address[] memory) {
        address[] memory protected = new address[](1);
        protected[0] = address(want);
        return protected;
    }

    modifier keepers() {
        require(
            msg.sender == address(keep3r) || msg.sender == address(strategy) || msg.sender == vault.governance() || msg.sender == IBaseStrategy(strategy).strategist(),
            "!keepers"
        );
        _;
    }

    // check if the current baseFee is below our external target
    function isBaseFeeAcceptable() internal view returns (bool) {
        return
            IBaseFee(0xb5e1CAcB567d98faaDB60a1fD4820720141f064F)
                .isCurrentBaseFeeAcceptable();
    }
   
    // ---------------------- YSWAPS FUNCTIONS ----------------------
    function setTradeFactory(address _tradeFactory) external onlyGovernance {
        if (tradeFactory != address(0)) {
            _removeTradeFactoryPermissions();
        }

        ITradeFactory tf = ITradeFactory(_tradeFactory);

        IERC20(comp).safeApprove(_tradeFactory, type(uint256).max);
        tf.enable(comp, address(want));
        
        tradeFactory = _tradeFactory;
    }

    function removeTradeFactoryPermissions() external management {
        _removeTradeFactoryPermissions();
    }

    function _removeTradeFactoryPermissions() internal {
        IERC20(comp).safeApprove(tradeFactory, 0);
        
        tradeFactory = address(0);
    }
}
