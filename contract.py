import smartpy as sp

# buyMap swapId -> {[address]: boolean}
# Where swapId is a unique swap on HEN
# still needs a lot of work defining data structures etc.

class HENDao(sp.Contract):
    def __init__(self, initOwners):
        self.init(owners = initOwners, locked=False, equity={}, buyMap={}, sellMap={})

    @sp.entry_point
    def buy_nft(self):
        hen_address = sp.address("KT1Hkg5qeNhfwpKW4fXvq7HGZB9z2EnmCCA9")
        c = sp.contract(sp.TPair(sp.TNat, sp.TNat), hen_address, entry_point = "collect").open_some();
        sp.transfer(sp.pair(1, 161619), sp.mutez(0), c);
    
    @sp.entry_point
    def deposit(self):
        self.data.equity[sp.sender] = sp.amount
    
    @sp.entry_point
    def propose_buy(self, params):
        sp.if self.data.buyMap.contains(params.swap_id):
            self.data.buyMap[params.swap_id][sp.sender] = True
        sp.else:
            props = {}
            sp.set_type(props, sp.TMap(sp.TAddress, sp.TBool));
            props[sp.sender] = True
            self.data.buyMap[params.swap_id] = props

if "templates" not in __name__:
    @sp.add_test(name = "HenDao")
    def test():
        c1 = HENDao([sp.address("tz1U6aFc7sZ3dfG5HfdWYmUFRbPw5A1FU3kX"), sp.address("tz1RxGRrxMdoushBUg4xD8X4dZVR2qASTJ9s")])
        scenario = sp.test_scenario()
        scenario.h1("Store Value")
        scenario += c1
        admin = sp.address("tz1U6aFc7sZ3dfG5HfdWYmUFRbPw5A1FU3kX")
        user2 = sp.address("tz1RxGRrxMdoushBUg4xD8X4dZVR2qASTJ9s")
        c1.deposit().run(sender=admin, amount= sp.mutez(10))
        scenario.verify(c1.data.equity[admin] == sp.mutez(10))
        c1.propose_buy(swap_id=123).run(sender=admin)
        c1.propose_buy(swap_id=123).run(sender=user2)

    # TODO Add the initial addresses here when deploying contract
    sp.add_compilation_target("henDao", HENDao([sp.address("tz1U6aFc7sZ3dfG5HfdWYmUFRbPw5A1FU3kX"), sp.address("tz1RxGRrxMdoushBUg4xD8X4dZVR2qASTJ9s")]))
