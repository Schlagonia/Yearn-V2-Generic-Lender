import pytest
import brownie
from OptV3.useful_methods import deposit, sleep, close
from brownie import Wei, reverts

#Strategy and Vault are imported after plugin has been plugged in
def test_logic(
    pluggedVault,
    pluggedStrategy,
    v3Plugin,
    gov,
    rando,
    weth,
    whale,
    chain
):

    strategy = pluggedStrategy
    vault = pluggedVault

    assert v3Plugin.hasAssets() == False
    assert v3Plugin.nav() == 0
    #Deposit
    amount = Wei("10 ether")
    deposit(amount, whale, weth, vault)

    strategy.harvest({"from":gov})
    assert v3Plugin.hasAssets() == True
    assert v3Plugin.nav() >= amount * .999
    assert v3Plugin.nav() == v3Plugin.underlyingBalanceStored()

    deposit(amount, whale, weth, vault)
    apr = v3Plugin.apr()
    aprAfter = v3Plugin.aprAfterDeposit(amount)
    assert apr > aprAfter
    
    strategy.harvest({"from":gov})
    newApr = v3Plugin.apr()
    assert close(aprAfter, newApr)

    nav = v3Plugin.nav()
    sleep(chain, 10)    
    newNav = v3Plugin.nav()
    assert newNav > nav

    #withdraw Some
    wethBal = weth.balanceOf(whale.address)
    vault.withdraw(amount, {"from": whale})
    wethAfterBal = weth.balanceOf(whale.address)
    assert wethBal + amount <= wethAfterBal

    a = v3Plugin.apr()
    n = v3Plugin.nav()

    assert v3Plugin.weightedApr() ==  a * n

    #withdraw all
    wethBal = weth.balanceOf(whale.address)
    sleep(chain, 100)
    vault.withdraw({"from":whale})
    wethAfterBal = weth.balanceOf(whale.address)

    assert wethBal + amount <= wethAfterBal
   


def test_emergency_withdraw(
    pluggedVault,
    pluggedStrategy,
    v3Plugin,
    gov,
    rando,
    whale,
    chain,
    weth
):
    strategy = pluggedStrategy
    vault = pluggedVault

    assert v3Plugin.hasAssets() == False
    assert v3Plugin.nav() == 0
    #Deposit
    amount = Wei("10 ether")
    deposit(amount, whale, weth, vault)

    strategy.harvest({"from":gov})
    assert v3Plugin.hasAssets() == True
    assert v3Plugin.nav() >= amount * .999
    assert v3Plugin.nav() == v3Plugin.underlyingBalanceStored()

    with brownie.reverts():
        v3Plugin.emergencyWithdraw(v3Plugin.nav(), {"from":rando})

    wethBal = weth.balanceOf(gov.address)
    toWithdraw = amount * .1
    v3Plugin.emergencyWithdraw(toWithdraw, {"from":gov})
    wethBalAfter = weth.balanceOf(gov.address)
    assert wethBalAfter - toWithdraw == wethBal

    wethBal = weth.balanceOf(gov.address)
    nav = v3Plugin.nav()
    v3Plugin.emergencyWithdraw(nav, {"from":gov})
    wethBalAfter = weth.balanceOf(gov.address)
    assert wethBalAfter - nav == wethBal

def test__withdrawAll(
    pluggedVault,
    pluggedStrategy,
    v3Plugin,
    gov,
    rando,
    whale,
    chain,
    weth
):
    strategy = pluggedStrategy
    vault = pluggedVault

    assert v3Plugin.hasAssets() == False
    assert v3Plugin.nav() == 0
    #Deposit
    amount = Wei("10 ether")
    deposit(amount, whale, weth, vault)

    strategy.harvest({"from":gov})
    assert v3Plugin.hasAssets() == True
    assert v3Plugin.nav() >= amount * .999
    assert v3Plugin.nav() == v3Plugin.underlyingBalanceStored()

    with brownie.reverts():
        v3Plugin.withdrawAll({"from":rando})


    wethBal = weth.balanceOf(v3Plugin.address)
    v3Plugin.withdrawAll({"from":gov})
    
    assert v3Plugin.underlyingBalanceStored() == 0;
    assert weth.balanceOf(strategy.address) > wethBal
