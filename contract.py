import smartpy as sp

# buyMap swapId -> {[address]: boolean}
# Where swapId is a unique swap on HEN
# still needs a lot of work defining data structures etc.

class HENDao(sp.Contract):
    def __init__(self, initOwners):
        # Owners are locked at initialization in this iteration
        # Future iterations could have dynamic owners
        self.init(owners = sp.set(initOwners), locked=False, equity={}, purchases=sp.set([]), buyMap={}, sellMap={})
    
    # TODO test this function
    def buy_nft(self, swap_id):
        hen_address = sp.address("KT1Hkg5qeNhfwpKW4fXvq7HGZB9z2EnmCCA9")
        c = sp.contract(sp.TPair(sp.TNat, sp.TNat), hen_address, entry_point = "collect").open_some();
        sp.transfer(sp.pair(1, swap_id), sp.mutez(0), c);
    
    @sp.entry_point
    def deposit(self):
        sp.if ~self.data.owners.contains(sp.sender):
            sp.failwith("not an owner")
        
        # Initialize equity or add to existing
        sp.if self.data.equity.contains(sp.sender):
            self.data.equity[sp.sender] += sp.amount
        sp.else:
            self.data.equity[sp.sender] = sp.amount
    
    @sp.entry_point
    def propose_buy(self, params):
        sp.if ~self.data.owners.contains(sp.sender):
            sp.failwith("not an owner")
        
        sp.if self.data.buyMap.contains(params.swap_id):
            self.data.buyMap[params.swap_id][sp.sender] = True
        sp.else:
            props = {}
            sp.set_type(props, sp.TMap(sp.TAddress, sp.TBool));
            props[sp.sender] = True
            self.data.buyMap[params.swap_id] = props
        
        # Everyone voted yes, execute the buy
        sp.if sp.len(self.data.buyMap[params.swap_id]) == sp.len(self.data.owners):
            self.buy_nft(params.swap_id)
            # The contract is locked once the first buy is executed
            # TODO, should the lock happen at a separate step?
            self.data.locked = True

if "templates" not in __name__:
    @sp.add_test(name = "Test_Deposit")
    def test():
        c1 = HENDao([sp.address("tz1owner1"), sp.address("tz1owner2")])
        scenario = sp.test_scenario()
        scenario.h1("Store Value")
        scenario += c1
        admin = sp.address("tz1owner1")
        user2 = sp.address("tz1owner2")
        hacker = sp.address("tz1hacker")
        c1.deposit().run(sender=admin, amount= sp.mutez(10))
        scenario.verify(c1.data.equity[admin] == sp.mutez(10))
        c1.deposit().run(sender=admin, amount= sp.mutez(5))
        scenario.verify(c1.data.equity[admin] == sp.mutez(15))
        c1.deposit().run(valid=False, sender=hacker, amount=sp.mutez(10))
        
        c1.propose_buy(swap_id=123).run(sender=admin)
        c1.propose_buy(swap_id=123).run(sender=user2)

    # TODO Add the initial addresses here when deploying contract
    sp.add_compilation_target("henDao", HENDao([]))
