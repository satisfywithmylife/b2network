
from main import B2Network
from web3 import Web3
from eth_account import Account
from config import my_file_name
import requests

# 创建evm钱包随机账户
ac = Account().create()
# 地址
address = ac.address
# 私钥
pk = ac.key.hex()
# 大号邀请码，换成自己的
code = 'ASDDDDD'

# 获取ip代理的链接，一次1个，文本格式，http协议, 填你自己的
ip_get_url = ''
proxy = requests.get(ip_get_url).text.strip()
print(proxy)
b2 = B2Network(pk=pk, invite_code=code, proxy=proxy)
# 注册登陆
b2.b2_login()
# 获取我的信息
my_invite_code = b2.get_user_info()['code']

# 保存账户信息，格式 地址----私钥----自己的邀请码
log_str = f'{address}----{pk}----{my_invite_code}'
B2Network.write_file(my_file_name, log_str)

# 用大号邀请码作为邀请人，绑定邀请关系
b2.invite()

# 领b2测试水龙头水，测试btc作为gas，需要代理
b2.b2_faucet()

# 合约领测试水，usdc（1000），usdt（1000），eth（1），必须先领测试btc水作为gas
b2.contract_faucet('usdc')
b2.contract_faucet('usdt')
b2.contract_faucet('eth')

# glowswap交换代币任务, 使用btc交换代币，coin只支持usdc，usdt, amount是btc的数量，主要不要超过钱包btc余额
b2.b2_glow_swap(coin='usdc', amount=0.00001)
# 添加流动性, 只能添加usdt-usdc稳定币池子，这里最好先领usdc水，我代码里面使用的是单边流动性，只需要钱包有usdc即可
b2.b2_glow_add_lp()

# layerbank 借贷, 抵押btc
b2.lend_supply(amount=0.0001)
# layerbank 借贷, 打开btc作为抵押物开关
b2.lend_enter_market()
# layerbank 借贷, 借usdc
b2.lend_borrow(amount=0.01)

# 刷新奥德赛点数(积分有延迟到账)
b2.claim_point()




