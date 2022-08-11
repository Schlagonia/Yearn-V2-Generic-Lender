from re import A
import pytest
import brownie

from brownie import Wei

from OptV3.useful_methods import deposit, sleep, close

def test_v3_clone(
    v3Plugin,
    GenericAaveV3,
    strategy,
    weth,
    router,
    router2,
    op
):
    
    tx = v3Plugin.cloneAaveLender(strategy, router, router2, v3Plugin.lenderName(), v3Plugin.isIncentivised())
    new_plugin = GenericAaveV3.at(tx.return_value)

    assert v3Plugin.want() == new_plugin.want()
    assert v3Plugin.lenderName() == new_plugin.lenderName()
    assert v3Plugin.isIncentivised() == new_plugin.isIncentivised()
    assert v3Plugin.aToken() == new_plugin.aToken()
    assert new_plugin.WNATIVE() == weth.address
    assert new_plugin.router() == router
    assert new_plugin.apr() == v3Plugin.apr()

def test_v3_clone_trigger(
    v3Plugin,
    GenericAaveV3,
    strategy,
    weth,
    router,
    router2,
    chain,
    whale,
    vault,
    gov
):
    
    tx = v3Plugin.cloneAaveLender(strategy, router, router2, v3Plugin.lenderName(), v3Plugin.isIncentivised())
    new_plugin = GenericAaveV3.at(tx.return_value)

 
    assert v3Plugin.want() == new_plugin.want()
    assert v3Plugin.lenderName() == new_plugin.lenderName()
    assert v3Plugin.isIncentivised() == new_plugin.isIncentivised()
    assert v3Plugin.aToken() == new_plugin.aToken()
    assert new_plugin.WNATIVE() == weth.address
    assert new_plugin.router() == router
    assert new_plugin.apr() == v3Plugin.apr()
    vault.addStrategy(strategy, 10_000, 0, 2 ** 256 - 1, 1_000, {"from":gov})
    strategy.addLender(new_plugin, {"from": gov})
    new_plugin.setMiddleSwapToken(weth, False, {"from": gov})
    deposit(10e18, whale, weth, vault)

    strategy.harvest({"from": gov})
    assert new_plugin.harvestTrigger("1") == False
    sleep(chain, 100)
    
    assert new_plugin.harvestTrigger("1") == True

def test_v3_clone_usdc(
    v3PluginUsdc,
    GenericAaveV3,
    strategyUsdc,
    weth,
    router,
    router2
):
    v3Plugin = v3PluginUsdc
    strategy = strategyUsdc
    
    tx = v3Plugin.cloneAaveLender(strategy, router, router2, v3Plugin.lenderName(), v3Plugin.isIncentivised())
    new_plugin = GenericAaveV3.at(tx.return_value)

    assert v3Plugin.want() == new_plugin.want()
    assert v3Plugin.lenderName() == new_plugin.lenderName()
    assert v3Plugin.isIncentivised() == new_plugin.isIncentivised()
    assert v3Plugin.aToken() == new_plugin.aToken()
    assert new_plugin.WNATIVE() == weth.address
    assert new_plugin.router() == router
    assert new_plugin.apr() == v3Plugin.apr()
    
def test_v3_clone_usdc_harvest(
    v3PluginUsdc,
    GenericAaveV3,
    strategyUsdc,
    usdc,
    router,
    router2,
    chain,
    whaleUsdc,
    vaultUsdc,
    gov,
    op,
):
    v3Plugin = v3PluginUsdc
    strategy = strategyUsdc
    
    tx = v3Plugin.cloneAaveLender(strategy, router, router2, v3Plugin.lenderName(), v3Plugin.isIncentivised())
    new_plugin = GenericAaveV3.at(tx.return_value)
    apr = v3Plugin.apr()

    assert v3Plugin.want() == new_plugin.want()
    assert v3Plugin.lenderName() == new_plugin.lenderName()
    assert v3Plugin.isIncentivised() == new_plugin.isIncentivised()
    assert v3Plugin.aToken() == new_plugin.aToken()
    assert new_plugin.router() == router

    vaultUsdc.addStrategy(strategy, 10_000, 0, 2 ** 256 - 1, 1_000, {"from":gov})
    strategy.addLender(new_plugin, {"from": gov})
    deposit(1000e6, whaleUsdc, usdc, vaultUsdc)
    strategy.harvest({"from": gov})
    assert new_plugin.harvestTrigger("1") == False
    sleep(chain, 100)
    assert new_plugin.harvestTrigger("1") == True 
    new_plugin.harvest({"from":gov})
    assert op.balanceOf(new_plugin.address) == 0


def test_double_initialize(
    v3Plugin,
    GenericAaveV3,
    strategy,
    strategist,
    weth,
    router,
    router2
):
    tx = v3Plugin.cloneAaveLender(strategy, router, router2, v3Plugin.lenderName(), v3Plugin.isIncentivised())
    new_plugin = GenericAaveV3.at(tx.return_value)

    with brownie.reverts():
        new_plugin.initialize(weth.address, router, router2, True, {"from":strategist})
