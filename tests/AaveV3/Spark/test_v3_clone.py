import pytest
import brownie

from brownie import Wei


def test_v3_clone(v3Plugin, GenericSpark, strategy, dai, weth, router, router2):

    tx = v3Plugin.cloneAaveLender(
        strategy, router, router2, v3Plugin.lenderName(), v3Plugin.isIncentivised()
    )
    new_plugin = GenericSpark.at(tx.return_value)

    assert v3Plugin.want() == new_plugin.want()
    assert v3Plugin.lenderName() == new_plugin.lenderName()
    assert v3Plugin.isIncentivised() == new_plugin.isIncentivised()
    assert v3Plugin.aToken() == new_plugin.aToken()
    assert v3Plugin.WNATIVE() == weth
    assert v3Plugin.router() == router


def test_double_initialize(
    v3Plugin, GenericSpark, strategy, strategist, dai, router, router2
):
    tx = v3Plugin.cloneAaveLender(
        strategy, router, router2, v3Plugin.lenderName(), v3Plugin.isIncentivised()
    )
    new_plugin = GenericSpark.at(tx.return_value)

    with brownie.reverts():
        new_plugin.initialize(dai.address, router, router2, True, {"from": strategist})
