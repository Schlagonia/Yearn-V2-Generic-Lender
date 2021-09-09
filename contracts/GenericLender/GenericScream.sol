// SPDX-License-Identifier: GPL-3.0
pragma solidity 0.6.12;
pragma experimental ABIEncoderV2;

import "../Interfaces/Compound/CErc20I.sol";
import "../Interfaces/Compound/ComptrollerI.sol";
import "../Interfaces/Compound/InterestRateModel.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/math/SafeMath.sol";
import "@openzeppelin/contracts/utils/Address.sol";
import "@openzeppelin/contracts/token/ERC20/SafeERC20.sol";

import "../Interfaces/UniswapInterfaces/IUniswapV2Router02.sol";

import "./GenericLenderBase.sol";

/********************
 *   A lender plugin for LenderYieldOptimiser for any erc20 asset on compound (not eth)
 *   Made by SamPriestley.com
 *   https://github.com/Grandthrax/yearnv2/blob/master/contracts/GenericDyDx/GenericCompound.sol
 *
 ********************* */

contract GenericScream is GenericLenderBase {
    using SafeERC20 for IERC20;
    using Address for address;
    using SafeMath for uint256;

    uint256 private constant blocksPerYear = 3154 * 10**4;
    address public constant spookyRouter = address(0xF491e7B69E4244ad4002BC14e878a34207E38c29);
    address public constant scream = address(0xe0654C8e6fd4D733349ac7E09f6f23DA256bF475);
    address public constant wftm = address(0x21be370D5312f44cB42ce377BC9b8a0cEF1A4C83);
    address public constant unitroller = address(0x260E596DAbE3AFc463e75B6CC05d8c46aCAcFB09);

    uint256 public dustThreshold;

    uint256 public minScreamToSell = 0 ether;

    CErc20I public cToken;

    constructor(
        address _strategy,
        string memory name,
        address _cToken
    ) public GenericLenderBase(_strategy, name) {
        _initialize(_cToken);
    }

    function initialize(address _cToken) external {
        _initialize(_cToken);
    }

    function _initialize(address _cToken) internal {
        require(address(cToken) == address(0), "GenericCream already initialized");
        cToken = CErc20I(_cToken);
        require(cToken.underlying() == address(want), "WRONG CTOKEN");
        want.safeApprove(_cToken, uint256(-1));
        IERC20(scream).safeApprove(spookyRouter, uint256(-1));
        dustThreshold = 10_000;
    }

    function cloneCompoundLender(
        address _strategy,
        string memory _name,
        address _cToken
    ) external returns (address newLender) {
        newLender = _clone(_strategy, _name);
        GenericScream(newLender).initialize(_cToken);
    }

    function nav() external view override returns (uint256) {
        return _nav();
    }

    //adjust dust threshol
    function setDustThreshold(uint256 amount) external management {
        dustThreshold = amount;
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
        uint256 currentCr = cToken.balanceOf(address(this));
        if (currentCr < dustThreshold) {
            balance = 0;
        } else {
            //The current exchange rate as an unsigned integer, scaled by 1e18.
            balance = currentCr.mul(cToken.exchangeRateStored()).div(1e18);
        }
    }

    function apr() external view override returns (uint256) {
        return _apr();
    }

    function _apr() internal view returns (uint256) {
        return (cToken.supplyRatePerBlock().add(compBlockShareInWant(0, false))).mul(blocksPerYear);
    }

    function compBlockShareInWant(uint256 change, bool add) public view returns (uint256){
        //comp speed is amount to borrow or deposit (so half the total distribution for want)
        uint256 distributionPerBlock = ComptrollerI(unitroller).compSpeeds(address(cToken));

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

        uint256 estimatedWant =  priceCheck(scream, address(want),blockShareSupply);
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
        address[] memory path = getTokenOutPath(start, end);
        uint256[] memory amounts = IUniswapV2Router02(spookyRouter).getAmountsOut(_amount, path);

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
        _disposeOfComp();
        looseBalance = want.balanceOf(address(this));
        want.safeTransfer(address(strategy), looseBalance);
        return looseBalance;
    }

    function _disposeOfComp() internal {

        CTokenI[] memory tokens = new CTokenI[](1);
        tokens[0] = cToken;

        ComptrollerI(unitroller).claimComp(address(this), tokens);

        uint256 _scream = IERC20(scream).balanceOf(address(this));

        if (_scream > minScreamToSell) {
            address[] memory path = getTokenOutPath(scream, address(want));
            IUniswapV2Router02(spookyRouter).swapExactTokensForTokens(_scream, uint256(0), path, address(this), now);
        }
    }

    function getTokenOutPath(address _token_in, address _token_out) internal pure returns (address[] memory _path) {
        bool is_wftm = _token_in == address(wftm) || _token_out == address(wftm);
        _path = new address[](is_wftm ? 2 : 3);
        _path[0] = _token_in;
        if (is_wftm) {
            _path[1] = _token_out;
        } else {
            _path[1] = address(wftm);
            _path[2] = _token_out;
        }
    }

    function deposit() external override management {
        uint256 balance = want.balanceOf(address(this));
        require(cToken.mint(balance) == 0, "ctoken: mint fail");
    }

    function withdrawAll() external override management returns (bool) {
        uint256 liquidity = want.balanceOf(address(cToken));
        uint256 liquidityInCTokens = convertFromUnderlying(liquidity);
        uint256 amountInCtokens = cToken.balanceOf(address(this));

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
        //return cToken.balanceOf(address(this)) > 0;
        return cToken.balanceOf(address(this)) > dustThreshold || want.balanceOf(address(this)) > 0;
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

    function protectedTokens() internal view override returns (address[] memory) {
        address[] memory protected = new address[](3);
        protected[0] = address(want);
        protected[1] = address(cToken);
        protected[2] = scream;
        return protected;
    }
}
