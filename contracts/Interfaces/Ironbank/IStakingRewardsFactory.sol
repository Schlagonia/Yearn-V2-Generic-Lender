// SPDX-License-Identifier: MIT

pragma solidity >=0.6.12;

interface IStakingRewardsFactory {
    function getStakingRewardsCount() external view returns (uint256);

    function getAllStakingRewards() external view returns (address[] memory);

    function getStakingRewards(address stakingToken)
        external
        view
        returns (address);

    function getStakingToken(address underlying)
        external
        view
        returns (address);
}