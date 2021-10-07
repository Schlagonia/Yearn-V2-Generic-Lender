from brownie import Wei

def test_triggers(
    wftm,
    scrWftm,
    chain,
    whale,
    vault,
    strategy,
    accounts,
    fn_isolation,
    GenericScream,
    Contract,
):
    strategist = accounts.at(strategy.strategist(), force=True)
    gov = accounts.at(vault.governance(), force=True)
    currency = wftm

    currency.approve(vault, 2 ** 256 - 1, {"from": whale})
    vault.addStrategy(strategy, 10_000, 0, 2 ** 256 - 1, 1_000, {"from": gov})

    whale_deposit = 1_000_000 * 1e18
    vault.deposit(whale_deposit, {"from": whale})
    chain.sleep(10)
    chain.mine(1)
    strategy.setWithdrawalThreshold(0, {"from": gov})

    strategy.harvest({"from": strategist})

    assert strategy.tendTrigger(1) == False
    assert strategy.tendTrigger(Wei("100_000_000 ether")) == False
    assert strategy.harvestTrigger(Wei("100_000_000 ether")) == False
    assert strategy.harvestTrigger(1) == False

    chain.sleep(3600*48)
    chain.mine(1)

    assert strategy.harvestTrigger(1) == True
