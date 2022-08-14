from OptV3.useful_methods import deposit, sleep, close
import pytest
from brownie import reverts, Contract, ZERO_ADDRESS
from weiroll import WeirollPlanner, WeirollContract


def test_yswaps(
    chain,
    token,
    vault,
    strategy,
    user,
    strategist,
    management,
    gov,
    amount,
    weth,
    usdc,
    RELATIVE_APPROX,
    trade_factory
):
    # Deposit to the vault
    user_balance_before = token.balanceOf(user)
    deposit(user, vault, token, amount)

    # harvest
    sleep(chain, 1)
    strategy.harvest({"from": strategist})
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount

    assert token.balanceOf(strategy) <= strategy.minWant()

    sleep(chain, 3 * 24 * 3600)
    
    assert strategy.estimatedRewardsInWant() > 0

    with reverts():
        strategy.setUpTradeFactory(trade_factory, {"from": management})

    assert strategy.tradeFactory() == ZERO_ADDRESS
    strategy.setUpTradeFactory(trade_factory, {"from": gov})
    assert strategy.tradeFactory() == trade_factory

    strategy.manualClaimRewards({"from": management})

    reward_tokens = [
        Contract(reward_token) for reward_token in strategy.getRewardTokens()
    ]
    router = WeirollContract.createContract(Contract(strategy.router()))
    receiver = strategy
    token_out = token

    planner = WeirollPlanner(trade_factory)

    token_bal_before = token.balanceOf(strategy)

    for reward_token in reward_tokens:
        print(reward_token.symbol())
        token_in = WeirollContract.createContract(reward_token)

        amount_in = reward_token.balanceOf(strategy)
        print(
            f"Executing trade {id}, tokenIn: {reward_token.symbol()} -> tokenOut {token.symbol()} w/ amount in {amount_in/1e18}"
        )

        route = []
        if token.symbol() == "WETH" or token.symbol() == "USDC":
            route = [(token_in.address, token.address, False)]
        elif token.symbol() == "DAI":
            route = [
                (token_in.address, usdc.address, False),
                (usdc.address, token.address, True),
            ]
        else:
            pytest.skip("Unknown path")

        planner.add(
            token_in.transferFrom(
                strategy.address,
                trade_factory.address,
                amount_in,
            )
        )

        planner.add(
            token_in.approve(
                router.address,
                amount_in,
            )
        )

        planner.add(
            router.swapExactTokensForTokens(
                amount_in,
                0,
                route,
                receiver.address,
                2**256 - 1,
            )
        )

    cmds, state = planner.plan()
    trade_factory.execute(cmds, state, {"from": trade_factory.governance()})

    token_bal_after = token.balanceOf(strategy)
    assert token_bal_after > token_bal_before

    tx = strategy.harvest({"from": strategist})
    assert tx.events["Harvested"]["profit"] > 0

    strategy.removeTradeFactoryPermissions({"from": management})
    assert strategy.tradeFactory() == ZERO_ADDRESS

    # withdrawal
    vault.withdraw({"from": user})
    assert (
        pytest.approx(token.balanceOf(user), rel=RELATIVE_APPROX) == user_balance_before
        or token.balanceOf(user) > user_balance_before
    )