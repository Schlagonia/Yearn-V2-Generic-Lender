import pytest
import brownie
from useful_methods import deposit, sleep
from brownie import Wei, reverts

def test_setup(
    v3Plugin,
    wavax
):

    numberOfRewardTokens  = v3Plugin.numberOfRewardTokens()
    assert v3Plugin.isIncentivised() == True
    assert numberOfRewardTokens == 1
    
    trigger = v3Plugin.harvestTrigger(100)
    assert trigger == False

def test_apr(
    v3Plugin,
    wavax,
    aWavax
):
    liq = wavax.balanceOf(aWavax)
    wavaxApr = v3Plugin._incentivesRate(liq, wavax.address)

    assert wavaxApr > 0


def test_harvest(
    pluggedVault,
    pluggedStrategy,
    v3Plugin,
    gov,
    rando,
    wavax,
    whale,
    chain
):
    strategy = pluggedStrategy
    vault = pluggedVault

    assert v3Plugin.hasAssets() == False
    assert v3Plugin.nav() == 0
    #Deposit
    amount = Wei("50 ether")
    deposit(amount, whale, wavax, vault)

    strategy.harvest({"from":gov})
    assert v3Plugin.hasAssets() == True
    assert v3Plugin.nav() >= amount * .999
    assert v3Plugin.nav() == v3Plugin.underlyingBalanceStored()

    assert v3Plugin.harvestTrigger('100') == False
    sleep(chain, 1000)
    assert v3Plugin.harvestTrigger('100') == True

    with brownie.reverts():
        v3Plugin.harvest({"from":rando})

    aBal = v3Plugin.underlyingBalanceStored()
    v3Plugin.harvest({"from":gov})
    #make sure the harvested was collected sold and reinvested 
    assert v3Plugin.harvestTrigger('100') == False
    assert wavax.balanceOf(v3Plugin.address) == 0
    assert aBal < v3Plugin.underlyingBalanceStored()

def test_harvest_usdc(
    pluggedVaultUsdc,
    pluggedStrategyUsdc,
    v3PluginUsdc,
    gov,
    rando,
    wavax,
    usdc,
    whaleUsdc,
    chain
):
    strategy = pluggedStrategyUsdc
    vault = pluggedVaultUsdc
    v3Plugin = v3PluginUsdc

    assert v3Plugin.hasAssets() == False
    assert v3Plugin.nav() == 0
    #Deposit
    #amount = Wei("50 ether")
    amount = 1e12
    deposit(amount, whaleUsdc, usdc, vault)

    strategy.harvest({"from":gov})
    assert v3Plugin.hasAssets() == True
    assert v3Plugin.nav() >= amount * .999
    assert v3Plugin.nav() == v3Plugin.underlyingBalanceStored()

    assert v3Plugin.harvestTrigger('100') == False
    sleep(chain, 1000)
    assert v3Plugin.harvestTrigger('100') == True

    with brownie.reverts():
        v3Plugin.harvest({"from":rando})

    aBal = v3Plugin.underlyingBalanceStored()
    v3Plugin.harvest({"from":gov})
    #make sure the harvested was collected sold and reinvested 
    assert v3Plugin.harvestTrigger('100') == False
    assert wavax.balanceOf(v3Plugin.address) == 0
    assert aBal < v3Plugin.underlyingBalanceStored()
