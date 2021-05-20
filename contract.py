import smartpy as sp

# buyMap swapId -> {[address]: boolean}
# Where swapId is a unique swap on HEN
# still needs a lot of work defining data structures etc.

class HENDao(sp.Contract):
    def __init__(self, initOwners):
        # Owners are locked at initialization in this iteration
        # Future iterations could have dynamic owners
        self.init(owners = sp.set(initOwners), locked=False, lock_votes={}, unlock_votes={}, equity={}, purchases=sp.set([]), buyMap={}, sellMap={})
    
    # Vote to lock the contract
    # Once everyone votes, then self.data.locked = True, deposits are disabled
    @sp.entry_point
    def vote_lock(self):
        pass
    
    # Vote to unlock the contract, which allows further deposits
    # This will allow further deposits if people want to go for another round
    # Note that this allows dilution/rebalancing of equity of NFTs that are not yet sold
    @sp.entry_point
    def vote_unlock(self):
        pass
    
    # Withdraw equity, regardless of state, and remove from owners.
    # Warning, cannot be undone!
    @sp.entry_point
    def respectfully_leave(self):
        pass
    
    
    # TODO test this function
    def buy_nft(self, swap_id):
        hen_address = sp.address("KT1Hkg5qeNhfwpKW4fXvq7HGZB9z2EnmCCA9")
        c = sp.contract(sp.TPair(sp.TNat, sp.TNat), hen_address, entry_point = "collect").open_some();
        sp.transfer(sp.pair(1, swap_id), sp.mutez(0), c);
    
    @sp.entry_point
    def deposit(self):
        sp.if ~self.data.owners.contains(sp.sender):
            sp.failwith("not an owner");
        
        sp.if self.data.locked:
            sp.failwith("contract locked");
        
        # Initialize equity or add to existing
        sp.if self.data.equity.contains(sp.sender):
            self.data.equity[sp.sender] += sp.amount
        sp.else:
            self.data.equity[sp.sender] = sp.amount
    
    @sp.entry_point
    def withdraw(self):
        pass
    
    # Vote for a specific "swap" on HEN
    # A swap is an objkt that is being sold at a specific price
    @sp.entry_point
    def vote_buy(self, params):
        sp.if ~self.data.owners.contains(sp.sender):
            sp.failwith("not an owner")
        
        sp.if ~self.data.locked:
            sp.failwith("can't buy when unlocked")
        
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
    
    # Undo a vote for a swap
    @sp.entry_point
    def undo_vote_buy(self):
        pass
    
    # Propose selling an objkt at a certain price point
    @sp.entry_point
    def propose_sell(self):
        pass
    
    # Vote for a proposal to sell an objkt
    @sp.entry_point
    def vote_sell(self):
        pass
    
    # Undo a vote for a proposal
    @sp.entry_point
    def undo_vote_sell(self):
        pass
    
    # Vote to cancel an existing swap
    @sp.entry_point
    def vote_cancel_sell(self):
        pass
    
    # Undo your vote to cancel an existing swap
    @sp.entry_point
    def undo_vote_cancel_sell(self):
        pass

if "templates" not in __name__:
    @sp.add_test(name = "Test_Deposit")
    def test():
        c1 = HENDao([sp.address("tz1owner1"), sp.address("tz1owner2")])
        scenario = sp.test_scenario()
        scenario.h1("Test Deposits")
        scenario += c1
        admin = sp.address("tz1owner1")
        user2 = sp.address("tz1owner2")
        hacker = sp.address("tz1hacker")
        c1.deposit().run(sender=admin, amount= sp.mutez(10))
        scenario.verify(c1.data.equity[admin] == sp.mutez(10))
        c1.deposit().run(sender=admin, amount= sp.mutez(5))
        scenario.verify(c1.data.equity[admin] == sp.mutez(15))
        c1.deposit().run(valid=False, sender=hacker, amount=sp.mutez(10))
    
    @sp.add_test(name = "Test_Buy")
    def test():
        c1 = HENDao([sp.address("tz1owner1"), sp.address("tz1owner2")])
        scenario = sp.test_scenario()
        scenario.h1("Test Buy")
        scenario += c1
        admin = sp.address("tz1owner1")
        user2 = sp.address("tz1owner2")

        scenario.h2("Buying disabled when locked")
        c1.vote_buy(swap_id=123).run(valid=False, sender=admin)
        
        scenario.h2("Buying enabled when unlocked")
        # TODO write this test

    # TODO Add the initial addresses here when deploying contract
    sp.add_compilation_target("henDao", HENDao([]))
