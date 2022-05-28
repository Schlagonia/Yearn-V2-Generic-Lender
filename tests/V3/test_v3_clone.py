import pytest
import brownie

from brownie import Wei

def test_v3_clone(
    v3Plugin,
    GenericAaveV3,
    strategy
):
    
    tx = v3Plugin.cloneAaveLender(strategy, v3Plugin.lenderName(), v3Plugin.isIncentivised())
    new_plugin = GenericAaveV3.at(tx.return_value)

    assert v3Plugin.want() == new_plugin.want()
    assert v3Plugin.lenderName() == new_plugin.lenderName()
    assert v3Plugin.isIncentivised() == new_plugin.isIncentivised()
    assert  v3Plugin.numberOfRewardTokens() ==  new_plugin.numberOfRewardTokens()
    assert v3Plugin.aToken() == new_plugin.aToken()
    

def test_double_initialize(
    v3Plugin,
    GenericAaveV3,
    strategy,
    strategist
):
    tx = v3Plugin.cloneAaveLender(strategy, v3Plugin.lenderName(), v3Plugin.isIncentivised())
    new_plugin = GenericAaveV3.at(tx.return_value)

    with brownie.reverts():
        new_plugin.initialize(True, {"from":strategist})
