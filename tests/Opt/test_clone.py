from re import A
import pytest
import brownie
import random
from brownie import Wei

from Opt.useful_methods import deposit, sleep, close

def test_v3_clone(
    plugin,
    GenericIronBank,
    strategy,
    weth,
    router,
    router2,
    op
):
    
    tx = plugin.cloneIronBankLender(strategy, plugin.lenderName())
    new_plugin = GenericIronBank.at(tx.return_value)

    assert plugin.want() == new_plugin.want()
    assert plugin.lenderName() == new_plugin.lenderName()
    assert plugin.cToken() == new_plugin.cToken()
    assert new_plugin.WNATIVE() == weth.address
    assert new_plugin.apr() == plugin.apr()
    assert new_plugin.ignorePrinting() == True

def test_clone_trigger(
    plugin,
    GenericIronBank,
    strategy,
    weth,
    router,
    router2,
    chain,
    whale,
    vault,
    gov,
    ib,
    whaleIb
):
    
    tx = plugin.cloneIronBankLender(strategy, plugin.lenderName())
    new_plugin = GenericIronBank.at(tx.return_value)

 
    assert plugin.want() == new_plugin.want()
    assert plugin.lenderName() == new_plugin.lenderName()
    assert plugin.cToken() == new_plugin.cToken()
    assert new_plugin.WNATIVE() == weth.address
    assert new_plugin.apr() == plugin.apr()
    vault.addStrategy(strategy, 10_000, 0, 2 ** 256 - 1, 1_000, {"from":gov})
    strategy.addLender(new_plugin, {"from": gov})
    new_plugin.setMiddleSwapToken(weth, False, {"from": gov})
    deposit(10e18, whale, weth, vault)

    strategy.harvest({"from": gov})
    assert new_plugin.harvestTrigger("1000000000") == False
    sleep(chain, 1)
    ib.transfer(new_plugin.address, 100e18, {"from": whaleIb})
    
    assert new_plugin.harvestTrigger("1000000000") == True

def test_clone_usdc(
    plugin,
    GenericIronBank,
    strategyUsdc,
    weth,
    router,
    router2,usdc
):
    #plugin = pluginUsdc
    strategy = strategyUsdc
    
    tx = plugin.cloneIronBankLender(strategy, plugin.lenderName())
    new_plugin = GenericIronBank.at(tx.return_value)

    assert usdc == new_plugin.want()
    assert plugin.lenderName() == new_plugin.lenderName()
    assert plugin.ignorePrinting() == new_plugin.ignorePrinting()
    #assert plugin.cToken() == new_plugin.cToken()
    assert new_plugin.WNATIVE() == weth.address
    assert new_plugin.apr() > 0
    
def test_clone_harvest(
    pluginUsdc,
    GenericIronBank,
    strategyUsdc,
    strategy,
    usdc,
    router,
    router2,
    chain,
    whaleUsdc,
    vault,
    gov,
    op,
    weth,
    ib,
    whaleIb,
    whale
):
    plugin = pluginUsdc
    #strategy = strategyUsdc
    
    tx = plugin.cloneIronBankLender(strategy, plugin.lenderName())
    new_plugin = GenericIronBank.at(tx.return_value)
    apr = plugin.apr()

    assert weth == new_plugin.want()
    assert plugin.lenderName() == new_plugin.lenderName()
    assert plugin.ignorePrinting() == new_plugin.ignorePrinting()

    vault.addStrategy(strategy, 10_000, 0, 2 ** 256 - 1, 1_000, {"from":gov})
    strategy.addLender(new_plugin, {"from": gov})
    deposit(10e6, whale, weth, vault)
    strategy.harvest({"from": gov})
    assert new_plugin.harvestTrigger("100000000") == False
    sleep(chain, 1)
    ib.transfer(new_plugin.address, 100e18, {"from": whaleIb})
    assert new_plugin.harvestTrigger("100000000") == True 
    before_bal = new_plugin.underlyingBalanceStored()
    before_stake = new_plugin.stakedBalance()
    new_plugin.harvest({"from":gov})
    assert ib.balanceOf(new_plugin.address) == 0
    assert before_bal < new_plugin.underlyingBalanceStored()
    assert before_stake < new_plugin.stakedBalance()


def test_double_initialize(
    plugin,
    GenericIronBank,
    strategy,
    strategist,
    weth,
    router,
    router2
):
    tx = plugin.cloneIronBankLender(strategy, plugin.lenderName())
    new_plugin = GenericIronBank.at(tx.return_value)

    with brownie.reverts():
        new_plugin.initialize({"from":strategist})


def test_clone(
    chain,
    usdc,
    whaleUsdc,
    gov,
    strategist,
    rando,
    vaultUsdc,
    OptStrategy,
    pluggedStrategyUsdc,
    GenericIronBank,
    cUsdc,
):
    strategy = pluggedStrategyUsdc
    vault = vaultUsdc
    whale = whaleUsdc
    # Clone magic
    tx = strategy.clone(vault)
    cloned_strategy = OptStrategy.at(tx.return_value)
    cloned_strategy.setWithdrawalThreshold(
        strategy.withdrawalThreshold(), {"from": gov}
    )
    cloned_strategy.setDebtThreshold(strategy.debtThreshold(), {"from": gov})
    cloned_strategy.setProfitFactor(strategy.profitFactor(), {"from": gov})
    cloned_strategy.setMaxReportDelay(strategy.maxReportDelay(), {"from": gov})

    assert cloned_strategy.numLenders() == 0

    # Clone the Comp lender
    original_comp = GenericIronBank.at(strategy.lenders(strategy.numLenders() - 1))
    tx = original_comp.cloneIronBankLender(
        cloned_strategy, "ClonedIBUSDC", {"from": gov}
    )
    cloned_lender = GenericIronBank.at(tx.return_value)
    assert cloned_lender.lenderName() == "ClonedIBUSDC"

    cloned_strategy.addLender(cloned_lender, {"from": gov})
    
    with brownie.reverts():
        cloned_lender.initialize( {'from': gov})

    starting_balance = usdc.balanceOf(strategist)
    currency = usdc
    decimals = currency.decimals()

    usdc.approve(vault, 2 ** 256 - 1, {"from": whale})
    usdc.approve(vault, 2 ** 256 - 1, {"from": strategist})

    deposit_limit = 1_000_000_000 * (10 ** (decimals))
    debt_ratio = 10_000
    vault.addStrategy(cloned_strategy, debt_ratio, 0, 2 ** 256 - 1, 500, {"from": gov})
    vault.setDepositLimit(deposit_limit, {"from": gov})

    assert deposit_limit == vault.depositLimit()
    # our humble strategist deposits some test funds
    depositAmount = 501 * (10 ** (decimals))
    usdc.transfer(strategist, depositAmount, {"from": whale})
    vault.deposit(depositAmount, {"from": strategist})

    assert cloned_strategy.estimatedTotalAssets() == 0
    chain.mine(1)
    assert cloned_strategy.harvestTrigger(1) == True

    cloned_strategy.harvest({"from": strategist})

    assert (
        cloned_strategy.estimatedTotalAssets() >= depositAmount * 0.999999
    )  # losing some dust is ok

    assert cloned_strategy.harvestTrigger(1) == False

    # whale deposits as well
    whale_deposit = 100_000 * (10 ** (decimals))
    vault.deposit(whale_deposit, {"from": whale})
    assert cloned_strategy.harvestTrigger(1000) == True

    cloned_strategy.harvest({"from": strategist})

    for i in range(15):
        waitBlock = random.randint(10, 50)
        chain.sleep(15 * 30)
        chain.mine(waitBlock)

        cloned_strategy.harvest({"from": strategist})
        chain.sleep(6 * 3600 + 1)  # to avoid sandwich protection
        chain.mine(1)

        action = random.randint(0, 9)
        if action < 3:
            percent = random.randint(50, 100)

            shareprice = vault.pricePerShare()

            shares = vault.balanceOf(whale)
            print("whale has:", shares)
            sharesout = int(shares * percent / 100)
            expectedout = sharesout * (shareprice / 1e18) * (10 ** (decimals * 2))

            balanceBefore = currency.balanceOf(whale)
            vault.withdraw(sharesout, {"from": whale})
            chain.mine(waitBlock)
            balanceAfter = currency.balanceOf(whale)

            withdrawn = balanceAfter - balanceBefore
            assert withdrawn > expectedout * 0.99 and withdrawn < expectedout * 1.01

        elif action < 5:
            depositAm = random.randint(10, 100) * (10 ** decimals)
            vault.deposit(depositAm, {"from": whale})

    # strategist withdraws
    shareprice = vault.pricePerShare()

    shares = vault.balanceOf(strategist)
    expectedout = shares * (shareprice / 1e18) * (10 ** (decimals * 2))
    balanceBefore = currency.balanceOf(strategist)

    status = cloned_strategy.lendStatuses()
    form = "{:.2%}"
    formS = "{:,.0f}"
    for j in status:
        print(
            f"Lender: {j[0]}, Deposits: {formS.format(j[1]/1e6)}, APR: {form.format(j[2]/1e18)}"
        )
    vault.withdraw(vault.balanceOf(strategist), {"from": strategist})
    balanceAfter = currency.balanceOf(strategist)
    status = cloned_strategy.lendStatuses()

    chain.mine(waitBlock)
    withdrawn = balanceAfter - balanceBefore
    assert withdrawn > expectedout * 0.99 and withdrawn < expectedout * 1.01

    profit = balanceAfter - starting_balance
    assert profit > 0
    print(profit)
