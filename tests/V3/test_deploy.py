from pyrsistent import inc
import pytest
import brownie

from brownie import Wei, GenericAaveV3

def test_deploy(strategist, strategy, GenericAaveV3, wftm, aWftm, lendingPool, router):
    incentivize = False

    v3Plugin = strategist.deploy(GenericAaveV3, strategy, wftm.address, router, "AaveV3", incentivize)

    incentivized = v3Plugin.isIncentivised()
    numberOfRewardTokens = v3Plugin.numberOfRewardTokens()
    aToken = v3Plugin.aToken()
    allowance = wftm.allowance(v3Plugin.address, lendingPool)
    native = v3Plugin.WNATIVE()
    _router = v3Plugin.router()

    assert incentivized == incentivize
    assert numberOfRewardTokens == 0
    assert native == wftm.address
    assert _router == router
    assert aToken == aWftm
    assert allowance == 2**256-1

def test_deploy_incentivized(strategist, strategy, GenericAaveV3, wftm, aWftm, router, lendingPool):
    incentivize = True

    v3Plugin = strategist.deploy(GenericAaveV3, strategy, wftm.address, router, "AaveV3", incentivize)

    incentivized = v3Plugin.isIncentivised()
    numberOfRewardTokens = v3Plugin.numberOfRewardTokens()
    aToken = v3Plugin.aToken()
    allowance = wftm.allowance(v3Plugin.address, lendingPool)

    assert incentivized == incentivize
    # Will still have no reward tokens even if we set it to incentivized with current Aave set up
    assert numberOfRewardTokens == 0
    assert aToken == aWftm
    assert allowance == 2**256-1

def test_adding_plugIn(
    strategy,
    v3Plugin,
    gov
):
    strategy.addLender(v3Plugin, {"from" : gov})
    assert strategy.numLenders() == 1
    assert v3Plugin.strategy() == strategy.address
    assert v3Plugin.want() == strategy.want()
    assert v3Plugin.vault() == v3Plugin.vault()

def test_reinitialize(
    v3Plugin,
    wftm,
    router
):
    with brownie.reverts():
        v3Plugin.initialize(wftm.address, router, False)
