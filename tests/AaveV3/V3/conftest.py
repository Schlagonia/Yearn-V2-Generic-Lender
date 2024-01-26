import pytest
from brownie import Wei, config, Contract


@pytest.fixture
def wftm():
    yield Contract("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2")


@pytest.fixture
def aWftm():
    yield "0x4d5F47FA6A74757f35C14fD3a6Ef8E3C9BC514E8"


@pytest.fixture
def lendingPool():
    yield "0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2"


@pytest.fixture
def router():
    yield "0xd9e1cE17f2641f24aE83637ab66a2cca9C378B9F"


@pytest.fixture
def router2():
    yield "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"


@pytest.fixture
def gov(accounts):
    yield accounts[3]


@pytest.fixture
def whale(accounts):
    yield accounts.at("0xBA12222222228d8Ba445958a75a0704d566BF2C8", force=True)


@pytest.fixture
def rewards(gov):
    yield gov  # TODO: Add rewards contract


@pytest.fixture
def guardian(accounts):
    # YFI Whale, probably
    yield accounts[2]


@pytest.fixture
def strategist(accounts):
    # YFI Whale, probably
    yield accounts[2]


@pytest.fixture
def keeper(accounts):
    # This is our trusty bot!
    yield accounts[4]


@pytest.fixture
def rando(accounts):
    yield accounts[9]


@pytest.fixture
def realVault(pm):
    Vault = pm(config["dependencies"][0]).Vault
    realVault = Vault.at("0xC1f3C276Bf73396C020E8354bcA581846171649d")
    yield realVault


@pytest.fixture
def vault(gov, rewards, guardian, wftm, pm):
    Vault = pm(config["dependencies"][0]).Vault
    vault = Vault.deploy({"from": guardian})
    vault.initialize(wftm, gov, rewards, "", "")
    vault.setDepositLimit(2 ** 256 - 1, {"from": gov})

    yield vault


@pytest.fixture
def realStrategy(FtmStrategy):
    realStrategy = FtmStrategy.at("0x23c7DB62d07425733a0F61B4b2039b27Fd3cD0B1")
    yield realStrategy


@pytest.fixture
def strategy(
    strategist,
    keeper,
    vault,
    gov,
    FtmStrategy,
):
    strategy = strategist.deploy(FtmStrategy, vault)
    strategy.setKeeper(keeper)

    assert strategy.numLenders() == 0
    yield strategy


@pytest.fixture
def v3Plugin(strategist, GenericAaveV3, strategy, wftm, router, router2):
    v3Plugin = strategist.deploy(
        GenericAaveV3, strategy, wftm.address, router, router2, "AaveV3", False
    )

    assert v3Plugin.underlyingBalanceStored() == 0
    apr = v3Plugin.apr()
    assert apr > 0
    print(apr / 1e18)

    apr2 = v3Plugin.aprAfterDeposit(5_000 * 1e18)  # * 3154 * 10**4
    print(apr2 / 1e18)
    assert apr2 < apr
    yield v3Plugin


@pytest.fixture
def pluggedStrategy(strategy, v3Plugin, gov):
    strategy.addLender(v3Plugin, {"from": gov})
    assert strategy.numLenders() == 1
    pluggedStrategy = strategy
    yield pluggedStrategy


@pytest.fixture
def pluggedVault(pluggedStrategy, vault, gov):
    vault.addStrategy(pluggedStrategy, 10_000, 0, 2 ** 256 - 1, 1_000, {"from": gov})
    pluggedVault = vault
    yield pluggedVault
