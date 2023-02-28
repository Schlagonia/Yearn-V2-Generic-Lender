// SPDX-License-Identifier: GPL-3.0
pragma solidity 0.6.12;

import "./IWantToEth.sol";


interface AggregatorV3Interface {
    function latestAnswer() external view returns (uint256);
}

contract stEthOracle is IWantToEth {

    // returns the price of stEth to Eth in 1e18
    address public constant priceFeed = 0x86392dC19c0b719886221c78AB11eb8Cf5c52812;

    function wantToEth(uint256 input) external view override returns (uint256) {
        uint256 answer = AggregatorV3Interface(priceFeed).latestAnswer();
        require(answer != 0, "0 response");
        return input * 1e18 / answer;
    }

    function ethToWant(uint256 input) external view override returns (uint256) {
        uint256 answer = AggregatorV3Interface(priceFeed).latestAnswer();
        require(answer != 0, "0 response");
        return input * answer  / 1e18;
    }

}