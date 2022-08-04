from pyrsistent import inc
import pytest
import brownie

from brownie import Wei, GenericAaveV3

def test_deploy(strategist, strategy, GenericAaveV3, weth, aWeth, lendingPool, router, router2):
    incentivize = False

    v3Plugin = strategist.deploy(GenericAaveV3, strategy, weth.address, router, router2, "AaveV3", incentivize)

    incentivized = v3Plugin.isIncentivised()
    aToken = v3Plugin.aToken()
    allowance = weth.allowance(v3Plugin.address, lendingPool)
    native = v3Plugin.WNATIVE()
    _router = v3Plugin.router()

    assert incentivized == incentivize
    assert native == weth.address
    assert _router == router
    assert aToken == aWeth
    assert allowance == 2**256-1

def test_deploy_incentivized(strategist, strategy, GenericAaveV3, weth, aWeth, router, router2, lendingPool):
    incentivize = True

    v3Plugin = strategist.deploy(GenericAaveV3, strategy, weth.address, router, router2, "AaveV3", incentivize)

    incentivized = v3Plugin.isIncentivised()
    aToken = v3Plugin.aToken()
    allowance = weth.allowance(v3Plugin.address, lendingPool)

    assert incentivized == incentivize
    assert aToken == aWeth
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
    weth,
    router,
    router2
):
    with brownie.reverts():
        v3Plugin.initialize(weth.address, router, router2, False)
