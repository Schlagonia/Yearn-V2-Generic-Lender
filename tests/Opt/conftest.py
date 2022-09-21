import pytest
from brownie import Wei, config, Contract

@pytest.fixture
def weth():
    yield Contract("0x4200000000000000000000000000000000000006")

@pytest.fixture
def usdc():
    yield Contract("0x7F5c764cBc14f9669B88837ca1490cCa17c31607")

@pytest.fixture
def aWeth():
    yield "0xe50fA9b3c56FfB159cB0FCA61F5c9D750e8128c8"

@pytest.fixture
def cUsdc():
    yield Contract("0x1d073cf59Ae0C169cbc58B6fdD518822ae89173a")

@pytest.fixture
def ib():
    yield Contract("0x00a35FD824c717879BF370E70AC6868b95870Dfb")

@pytest.fixture
def op():
    yield Contract("0x4200000000000000000000000000000000000042")

@pytest.fixture
def lendingPool():
    yield '0x794a61358D6845594F94dc1DB02A252b5b4814aD'

@pytest.fixture
def router():
    yield '0xa132DAB612dB5cB9fC9Ac426A0Cc215A3423F9c9'

@pytest.fixture
def router2(accounts):
    yield "0xa132DAB612dB5cB9fC9Ac426A0Cc215A3423F9c9"

@pytest.fixture
def gov(accounts):
    yield accounts[3]

@pytest.fixture
def whale(accounts):
    yield accounts.at("0x73B14a78a0D396C521f954532d43fd5fFe385216", force=True)

@pytest.fixture
def whaleUsdc(accounts):
    yield accounts.at("0xEbe80f029b1c02862B9E8a70a7e5317C06F62Cae", force=True)

@pytest.fixture
def whaleIb(accounts):
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
def vault(gov, rewards, guardian, weth, pm):
    Vault = pm(config["dependencies"][0]).Vault
    vault = Vault.deploy({"from": guardian})
    vault.initialize(weth, gov, rewards, "", "")
    vault.setDepositLimit(2**256-1, {"from": gov})

    yield vault

@pytest.fixture
def vaultUsdc(gov, rewards, guardian, usdc, pm):
    Vault = pm(config["dependencies"][0]).Vault
    vaultUsdc = Vault.deploy({"from": guardian})
    vaultUsdc.initialize(usdc, gov, rewards, "", "")
    vaultUsdc.setDepositLimit(2**256-1, {"from": gov})

    yield vaultUsdc

@pytest.fixture
def strategy(
    strategist,
    keeper,
    vault,
    gov,
    OptStrategy,
):
    strategy = strategist.deploy(OptStrategy, vault)
    strategy.setKeeper(keeper)

    assert strategy.numLenders() == 0
    yield strategy

@pytest.fixture
def strategyUsdc(
    strategist,
    keeper,
    vaultUsdc,
    gov,
    OptStrategy,
):
    strategyUsdc = strategist.deploy(OptStrategy, vaultUsdc)
    strategyUsdc.setKeeper(keeper)
    strategyUsdc.setWithdrawalThreshold(100, {"from": gov})

    assert strategyUsdc.numLenders() == 0
    yield strategyUsdc

@pytest.fixture
def plugin(
    strategist,
    GenericIronBank,
    strategy
):
    plugin = strategist.deploy(
        GenericIronBank, 
        strategy,
        "IronBankPlugin"
    )

    assert plugin.underlyingBalanceStored() == 0
    apr = plugin.apr()
    assert apr > 0
    print(apr/1e18)
    
    apr2 = plugin.aprAfterDeposit(5_000 * 1e18) # * 3154 * 10**4
    print(apr2/1e18)
    assert apr2 < apr
    yield plugin

@pytest.fixture
def pluginUsdc(
    strategist,
    GenericIronBank,
    strategyUsdc,

):
    pluginUsdc = strategist.deploy(
        GenericIronBank, 
        strategyUsdc,
        "IronBankPlugin"
    )

    assert pluginUsdc.underlyingBalanceStored() == 0
    apr = pluginUsdc.apr()
    assert apr > 0
    print(apr/1e18)
    
    apr2 = pluginUsdc.aprAfterDeposit(5_000 * 1e18) # * 3154 * 10**4
    print(apr2/1e18)
    assert apr2 < apr
    yield pluginUsdc


@pytest.fixture
def pluggedStrategy(
    strategy,
    plugin,
    gov
):
    strategy.addLender(plugin, {"from":gov})
    assert strategy.numLenders() == 1
    pluggedStrategy = strategy
    yield pluggedStrategy

@pytest.fixture
def pluggedStrategyUsdc(
    strategyUsdc,
    pluginUsdc,
    gov
):
    strategyUsdc.addLender(pluginUsdc, {"from":gov})
    assert strategyUsdc.numLenders() == 1
    pluggedStrategyUsdc = strategyUsdc
    yield pluggedStrategyUsdc

@pytest.fixture
def pluggedVault(
    pluggedStrategy,
    vault,
    gov
):
    vault.addStrategy(pluggedStrategy, 10_000, 0, 2 ** 256 - 1, 1_000, {"from":gov})
    pluggedVault = vault
    yield pluggedVault

@pytest.fixture
def pluggedVaultUsdc(
    pluggedStrategyUsdc,
    vaultUsdc,
    gov
):
    vaultUsdc.addStrategy(pluggedStrategyUsdc, 10_000, 0, 2 ** 256 - 1, 1_000, {"from":gov})
    pluggedVaultUsdc = vaultUsdc
    yield pluggedVaultUsdc

@pytest.fixture
def trade_factory():
    yield Contract("0x21d7B09Bcf08F7b6b872BED56cB32416AE70bCC8")