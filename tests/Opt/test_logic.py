import pytest
import brownie
from Opt.useful_methods import deposit, sleep, close
from brownie import Wei, reverts, Contract

#Strategy and Vault are imported after plugin has been plugged in
def test_logic(
    pluggedVault,
    pluggedStrategy,
    plugin,
    gov,
    rando,
    weth,
    whale,
    chain,
    cUsdc
):

    strategy = pluggedStrategy
    vault = pluggedVault
    cToken = Contract(plugin.cToken())
    assert plugin.hasAssets() == False
    assert plugin.nav() == 0
    #Deposit
    amount = Wei("10 ether")
    deposit(amount, whale, weth, vault)

    strategy.harvest({"from":gov})
    assert plugin.hasAssets() == True
    assert plugin.nav() >= amount * .999
    assert plugin.nav() == plugin.underlyingBalanceStored()
    sleep(chain, 2)
    deposit(amount, whale, weth, vault)
    apr = plugin.apr()
    aprAfter = plugin.aprAfterDeposit(amount)
    assert apr > aprAfter
    
    strategy.harvest({"from":gov})
    newApr = plugin.apr()
    assert close(aprAfter, newApr)

    nav = plugin.nav()
    sleep(chain, 10)
    cToken.accrueInterest({"from": gov})
    newNav = plugin.nav()
    assert newNav > nav

    #withdraw Some
    wethBal = weth.balanceOf(whale.address)
    vault.withdraw(amount, {"from": whale})
    wethAfterBal = weth.balanceOf(whale.address)
    assert wethBal + amount <= wethAfterBal

    a = plugin.apr()
    n = plugin.nav()

    assert plugin.weightedApr() ==  a * n

    #withdraw all
    wethBal = weth.balanceOf(whale.address)
    sleep(chain, 100)
    vault.withdraw({"from":whale})
    wethAfterBal = weth.balanceOf(whale.address)

    assert wethBal + amount <= wethAfterBal

def test_emergency_withdraw(
    pluggedVault,
    pluggedStrategy,
    plugin,
    gov,
    rando,
    whale,
    chain,
    weth
):
    strategy = pluggedStrategy
    vault = pluggedVault

    assert plugin.hasAssets() == False
    assert plugin.nav() == 0
    #Deposit
    amount = Wei("10 ether")
    deposit(amount, whale, weth, vault)

    strategy.harvest({"from":gov})
    assert plugin.hasAssets() == True
    assert plugin.nav() >= amount * .999
    assert plugin.nav() == plugin.underlyingBalanceStored()

    with brownie.reverts():
        plugin.emergencyWithdraw(plugin.nav(), {"from":rando})

    wethBal = weth.balanceOf(gov.address)
    toWithdraw = amount * .1
    plugin.emergencyWithdraw(toWithdraw, {"from":gov})
    wethBalAfter = weth.balanceOf(gov.address)
    assert wethBalAfter - toWithdraw == wethBal

    wethBal = weth.balanceOf(gov.address)
    nav = plugin.nav()
    plugin.emergencyWithdraw(nav, {"from":gov})
    wethBalAfter = weth.balanceOf(gov.address)
    assert wethBalAfter - nav == wethBal

def test_withdrawAll(
    pluggedVault,
    pluggedStrategy,
    plugin,
    gov,
    rando,
    whale,
    chain,
    weth
):
    strategy = pluggedStrategy
    vault = pluggedVault

    assert plugin.hasAssets() == False
    assert plugin.nav() == 0
    #Deposit
    amount = Wei("10 ether")
    deposit(amount, whale, weth, vault)

    strategy.harvest({"from":gov})
    assert plugin.hasAssets() == True
    assert plugin.nav() >= amount * .999
    assert plugin.nav() == plugin.underlyingBalanceStored()

    with brownie.reverts():
        plugin.withdrawAll({"from":rando})


    wethBal = weth.balanceOf(plugin.address)
    plugin.withdrawAll({"from":gov})
    
    assert plugin.underlyingBalanceStored() == 0;
    assert weth.balanceOf(strategy.address) > wethBal