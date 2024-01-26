from pyrsistent import inc
import pytest
import brownie
from brownie import Wei, GenericSpark


def test_deploy(
    strategist, strategy, GenericSpark, weth, dai, adai, lendingPool, router, router2
):
    incentivize = False

    v3Plugin = strategist.deploy(
        GenericSpark, strategy, weth, router, router2, "Spark", incentivize
    )

    incentivized = v3Plugin.isIncentivised()
    aToken = v3Plugin.aToken()
    allowance = dai.allowance(v3Plugin.address, lendingPool)
    native = v3Plugin.WNATIVE()
    _router = v3Plugin.router()

    assert incentivized == incentivize
    assert native == weth
    assert _router == router
    assert aToken == adai
    assert allowance == 2 ** 256 - 1


def test_adding_plugIn(strategy, v3Plugin, gov):
    strategy.addLender(v3Plugin, {"from": gov})
    assert strategy.numLenders() == 1
    assert v3Plugin.strategy() == strategy.address
    assert v3Plugin.want() == strategy.want()
    assert v3Plugin.vault() == v3Plugin.vault()


def test_reinitialize(v3Plugin, dai, router, router2):
    with brownie.reverts():
        v3Plugin.initialize(dai.address, router, router2, False)
