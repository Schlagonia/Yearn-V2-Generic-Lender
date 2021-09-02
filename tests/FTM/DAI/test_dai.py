from itertools import count
from brownie import Wei, reverts
from useful_methods import genericStateOfVault, genericStateOfStrat
import random
import brownie

def test_normal_activity(
    ftm_dai,
    scrDai,
    chain,
    whale,
    rando,
    vault,
    strategy,
    Contract,
    accounts,
    fn_isolation,
):
    strategist = accounts.at(strategy.strategist(), force=True)
    gov = accounts.at(vault.governance(), force=True)
    currency = ftm_dai
    starting_balance = currency.balanceOf(strategist)

    currency.approve(vault, 2 ** 256 - 1, {"from": whale})
    currency.approve(vault, 2 ** 256 - 1, {"from": strategist})

    deposit_limit = 10_000
    vault.addStrategy(strategy, deposit_limit, 0, 2 ** 256 - 1, 1000, {"from": gov})

    whale_deposit = 1_000_000 * 1e18
    vault.deposit(whale_deposit, {"from": whale})
    chain.sleep(10)
    chain.mine(1)
    strategy.setWithdrawalThreshold(0, {"from": gov})
    #assert strategy.harvestTrigger(1 * 1e18) == True
    print(whale_deposit / 1e18)
    status = strategy.lendStatuses()
    form = "{:.2%}"
    formS = "{:,.0f}"
    for j in status:
        print(
            f"Lender: {j[0]}, Deposits: {formS.format(j[1]/1e18)} APR: {form.format(j[2]/1e18)}"
        )


    strategy.harvest({"from": strategist})

    status = strategy.lendStatuses()
    form = "{:.2%}"
    formS = "{:,.0f}"
    for j in status:
        print(
            f"Lender: {j[0]}, Deposits: {formS.format(j[1]/1e18)} APR: {form.format(j[2]/1e18)}"
        )
    startingBalance = vault.totalAssets()
    for i in range(2):

        waitBlock = 25
        # print(f'\n----wait {waitBlock} blocks----')
        chain.mine(waitBlock)
        chain.sleep(waitBlock)
        # print(f'\n----harvest----')
        scrDai.mint(0,{"from": whale})
        strategy.harvest({"from": strategist})

        # genericStateOfStrat(strategy, currency, vault)
        # genericStateOfVault(vault, currency)

        profit = (vault.totalAssets() - startingBalance) / 1e6
        strState = vault.strategies(strategy)
        totalReturns = strState[7]
        totaleth = totalReturns / 1e6
        # print(f'Real Profit: {profit:.5f}')
        difff = profit - totaleth
        # print(f'Diff: {difff}')

        blocks_per_year = 3154 * 10**4
        assert startingBalance != 0
        time = (i + 1) * waitBlock
        assert time != 0
        apr = (totalReturns / startingBalance) * (blocks_per_year / time)
        assert apr > 0 and apr < 1
        # print(apr)
        print(f"implied apr: {apr:.8%}")

    vault.withdraw(vault.balanceOf(whale), {"from": whale})

    vBal = vault.balanceOf(strategy)
    assert vBal > 0
    print(vBal)
    vBefore = vault.balanceOf(strategist)
    vault.transferFrom(strategy, strategist, vBal, {"from": strategist})
    print(vault.balanceOf(strategist) - vBefore)
    assert vault.balanceOf(strategist) - vBefore > 0


def test_scream_up_down(
    usdt,
    Strategy,
    crUsdt,
    samdev,
    GenericCream,
    cUsdt,
    live_strat_weth_1,
    chain,
    whale,
    daddy,
    currency,
    strategist,
    rando,
    vault,
    Contract,
    accounts,
    fn_isolation,
    aUsdt,
):

    gov = accounts.at(vault.governance(), force=True)
    tx = live_strat_weth_1.clone(vault, {"from": strategist})
    strategy = Strategy.at(tx.return_value)
    
    strategy.setRewards(strategist, {"from": strategist})
    strategy.setWithdrawalThreshold(0, {"from": strategist})

    creamPlugin = strategist.deploy(GenericCream, strategy, "Cream", crUsdt)

    strategy.addLender(creamPlugin, {"from": gov})

    strategy.setDebtThreshold(1*1e6, {"from": gov})
    strategy.setProfitFactor(1500, {"from": gov})
    strategy.setMaxReportDelay(86000, {"from": gov})

    starting_balance = currency.balanceOf(strategist)

    decimals = currency.decimals()
    #print(vault.withdrawalQueue(1))

    #strat2 = Contract(vault.withdrawalQueue(1))

    currency.approve(vault, 2 ** 256 - 1, {"from": whale})
    currency.approve(vault, 2 ** 256 - 1, {"from": strategist})

    deposit_limit = 1_000_000_000 * (10 ** (decimals))
    debt_ratio = 10_000
    
    vault.addStrategy(strategy, debt_ratio, 0, 2 ** 256 - 1, 500, {"from": gov})
    vault.setDepositLimit(deposit_limit, {"from": gov})

    assert deposit_limit == vault.depositLimit()
    # our humble strategist deposits some test funds
    depositAmount = 501 * (10 ** (decimals))
    vault.deposit(depositAmount, {"from": strategist})

    assert strategy.estimatedTotalAssets() == 0
    chain.mine(1)

    strategy.harvest({"from": strategist})

    #assert (
    #    strategy.estimatedTotalAssets() >= depositAmount * 0.999999
    #)  # losing some dust is ok
    # whale deposits as well
    whale_deposit = 1_000_000 * (10 ** (decimals))
    vault.deposit(whale_deposit, {"from": whale})
    assert strategy.harvestTrigger(1000) == True

    strategy.harvest({"from": strategist})
    #strat2.harvest({"from": gov})
    status = strategy.lendStatuses()
    form = "{:.2%}"
    formS = "{:,.0f}"
    for j in status:
        print(
            f"Lender: {j[0]}, Deposits: {formS.format(j[1]/1e6)}, APR: {form.format(j[2]/1e18)}"
        )
    chain.mine(20)
    crUsdt.mint(0, {"from": strategist})


    vault.updateStrategyDebtRatio(strategy, 0, {"from": gov})
    strategy.harvest({"from": strategist})
    print(crUsdt.balanceOf(creamPlugin))
    print(creamPlugin.hasAssets())
    chain.mine(20)
    crUsdt.mint(0, {"from": strategist})
    chain.mine(10)
    strategy.harvest({"from": strategist})
    
    print(crUsdt.balanceOf(creamPlugin))
    print(creamPlugin.hasAssets())
    chain.mine(20)
    crUsdt.mint(0, {"from": strategist})

    chain.mine(10)
    strategy.harvest({"from": strategist})
    print(creamPlugin.hasAssets())
    print(crUsdt.balanceOf(creamPlugin))
    status = strategy.lendStatuses()
    for j in status:
        print(
            f"Lender: {j[0]}, Deposits: {formS.format(j[1]/1e6)}, APR: {form.format(j[2]/1e18)}"
        )
    chain.mine(20)
    crUsdt.mint(0, {"from": strategist})
    vault.updateStrategyDebtRatio(strategy, 10_000, {"from": gov})
    strategy.harvest({"from": strategist})

    strategy.harvest({"from": strategist})
    status = strategy.lendStatuses()
    for j in status:
        print(
            f"Lender: {j[0]}, Deposits: {formS.format(j[1]/1e6)}, APR: {form.format(j[2]/1e18)}"
        )




def test_revoke_all(
    dai,
    interface,
    samdev,
    Contract,
    Strategy,
    daddy,
    live_guest_list,
    GenericDyDx,
    GenericCream,
    live_vault_dai_030,
    live_strat_weth_032,
    live_strat_dai_030,
    live_dydxdai,
    live_creamdai,
    chain,
    whale,
    gov,
    weth,
    accounts,
    rando,
    fn_isolation,
):

    whale = accounts.at('0x014de182c147f8663589d77eadb109bf86958f13', force=True)
    gov = daddy
    currency = dai
    decimals = currency.decimals()
    strategist = samdev
    #dydxPlugin = strategist.deploy(GenericDyDx, strategy, "DyDx")
    #creamPlugin = strategist.deploy(GenericCream, strategy, "Cream", crDai)
    dydxPlugin = live_dydxdai
    creamPlugin = live_creamdai


    vault = live_vault_dai_030
    #tx = live_strat_weth_032.clone(vault, {'from': strategist})
    #strategy = Strategy.at(tx.events['Cloned']["clone"])
    strategy = Strategy.at(vault.withdrawalQueue(0))

    vault.revokeStrategy(strategy, {'from': gov})
    vault.removeStrategyFromQueue(s1, {'from': gov})
    #vault.updateStrategyDebtRatio(strategy, 0, {'from': gov})
    strategy.harvest({"from": strategist})
    genericStateOfStrat(strategy, currency, vault)
    genericStateOfVault(vault, currency)
