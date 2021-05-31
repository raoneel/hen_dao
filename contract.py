import smartpy as sp

# buy_proposals swapId -> {[address]: boolean}
# Where swapId is a unique swap on HEN
# still needs a lot of work defining data structures etc.

class HENDao(sp.Contract):
    def __init__(self, initOwners):
        # Owners are locked at initialization in this iteration
        # Future iterations could have dynamic owners
        self.init(
            owners = sp.set(initOwners),
            numOwners=sp.len(initOwners),
            locked=False,
            closed=False,
            lock_votes=sp.set(),
            close_votes=sp.set(),
            equity={},
            total_contributed=sp.mutez(0),
            balance=sp.mutez(0),
            buy_proposals=sp.map({}, sp.TNat, sp.TRecord(votes=sp.TSet(sp.TAddress), passed=sp.TBool)),
            swap_proposals={},
            cancel_swap_proposals={},
            swap_proposal_id=0,
            did_withdraw=sp.set([], sp.TAddress),
            hen_address = sp.address("KT1Hkg5qeNhfwpKW4fXvq7HGZB9z2EnmCCA9")
        )
    
    # Vote to lock the contract
    # Once everyone votes, then self.data.locked = True, deposits are disabled
    @sp.entry_point
    def vote_lock(self):
        # If contract is already locked, then fail.
        sp.if self.data.locked:
            sp.failwith("already locked");

        sp.if self.data.owners.contains(sp.sender):
            self.data.lock_votes.add(sp.sender)
        
        # If everyone voted, then set Locked to True,
        # record the state of equity, and reset vo
        sp.if sp.len(self.data.lock_votes) == self.data.numOwners:
            self.data.locked = True
    
    # Vote to close the contract
    # One closed, you can never use this contract for purchasing again
    # Unsold NFTs will be permanently locked into this contract
    @sp.entry_point
    def vote_close(self):
        sp.if ~self.data.locked:
            sp.failwith("can't close unless locked")

        sp.if ~self.data.owners.contains(sp.sender):
            sp.failwith("not owner")
        
        sp.if ~self.data.closed:
            sp.failwith("Already closed")
        
        self.data.close_votes.add(sp.sender)

        # If everyone voted, then set closed to True,
        sp.if sp.len(self.data.close_votes) == self.data.numOwners:
            self.data.closed = True
            
            # Lock in the final balance, used for calculating withdrawals
            self.data.balance = sp.balance
    
    @sp.entry_point
    def deposit(self):
        sp.if ~self.data.owners.contains(sp.sender):
            sp.failwith("not owner");
        
        sp.if self.data.locked:
            sp.failwith("contract locked");
        
        # Initialize equity or add to existing
        sp.if self.data.equity.contains(sp.sender):
            self.data.equity[sp.sender] += sp.amount
        sp.else:
            self.data.equity[sp.sender] = sp.amount

        # Keep track of the total contributed, for bookkeeping purposes
        self.data.total_contributed += sp.amount
    
    # Withdraw your money and then record that you have withdrew
    @sp.entry_point
    def withdraw(self):
        sp.if ~self.data.closed:
            sp.failwith("not closed")
        
        sp.if ~self.data.owners.contains(sp.sender):
            sp.failwith("not owner")
        
        sp.if ~self.data.equity.contains(sp.sender):
            sp.failwith("no equity")

        sp.if self.data.did_withdraw.contains(sp.sender):
            sp.failwith("already withdrew")
        
        percent = self.data.equity[sp.sender] / self.data.total_contributed
        amount = percent * self.data.balance

        # Send to caller
        # sp.send(sp.sender, amount)
        # self.data.did_withdraw.add(sp.sender)
        
    
    # Vote for a specific "swap" on HEN
    # A swap is an objkt that is being sold at a specific price
    @sp.entry_point
    def vote_buy(self, params):
        sp.if ~self.data.owners.contains(sp.sender):
            sp.failwith("not owner")
        
        sp.if ~self.data.locked:
            sp.failwith("fund not locked")

        sp.if self.data.closed:
            sp.failwith("fund closed")

        sp.if self.data.buy_proposals.contains(params.swap_id):
            # If already passed, then fail
            sp.if self.data.buy_proposals[params.swap_id].passed:
                sp.failwith("already passed")
            
            self.data.buy_proposals[params.swap_id].votes.add(sp.sender)
        sp.else:
            votes = sp.set()
            votes.add(sp.sender)
            self.data.buy_proposals[params.swap_id] = sp.record(votes=votes, passed=False)

        # Everyone voted yes, execute the buy
        sp.if sp.len(self.data.buy_proposals[params.swap_id].votes) == sp.len(self.data.owners):
            self.hen_collect(params.swap_id)
            self.data.buy_proposals[params.swap_id].passed = True

    # Undo a vote for a swap
    @sp.entry_point
    def undo_vote_buy(self, params):
        self.data.buy_proposals[params.swap_id].votes.remove(sp.sender)

    # Propose selling an objkt at a certain price point
    @sp.entry_point
    def propose_swap(self, objkt_amount, objkt_id, xtz_per_objkt):
        sp.set_type(objkt_amount, sp.TNat)
        sp.set_type(objkt_id, sp.TNat)
        sp.set_type(xtz_per_objkt, sp.TMutez)
        
        sp.if ~self.data.owners.contains(sp.sender):
            sp.failwith("not owner")

        sp.if ~self.data.locked:
            sp.failwith("fund not locked")

        self.data.swap_proposals[self.data.swap_proposal_id] = sp.record(objkt_amount=objkt_amount, objkt_id=objkt_id, xtz_per_objkt=xtz_per_objkt, votes=sp.set([sp.sender], sp.TAddress), passed=False)

        # Increment the proposal ID
        self.data.swap_proposal_id += 1
    
    # Vote for a proposal to sell an objkt
    # This will call HEN's swap() if everyone votes
    @sp.entry_point
    def vote_swap(self, swap_proposal_id):
        sp.set_type(swap_proposal_id, sp.TNat)

        sp.if ~self.data.owners.contains(sp.sender):
            sp.failwith("not owner")
        
        sp.if ~self.data.locked:
            sp.failwith("fund unlocked")

        sp.if ~self.data.swap_proposals.contains(swap_proposal_id):
            sp.failwith("swap doesn't exist")
        
        sp.if self.data.swap_proposals[swap_proposal_id].passed == True:
            sp.failwith("already passed");

        self.data.swap_proposals[swap_proposal_id].votes.add(sp.sender)
        
        sp.if sp.len(self.data.swap_proposals[swap_proposal_id].votes) == self.data.numOwners:
            self.hen_swap(swap_proposal_id)
            self.data.swap_proposals[swap_proposal_id].passed = True
    
    # Undo a vote for a proposal
    @sp.entry_point
    def undo_vote_swap(self, swap_proposal_id):
        sp.set_type(swap_proposal_id, sp.TNat)

        sp.if ~self.data.owners.contains(sp.sender):
            sp.failwith("not owner")
        
        sp.if ~self.data.locked:
            sp.failwith("fund unlocked")

        sp.if ~self.data.swap_proposals.contains(swap_proposal_id):
            sp.failwith("swap doesn't exist")
        
        sp.if self.data.swap_proposals[swap_proposal_id].passed == True:
            sp.failwith("already passed");

        self.data.swap_proposals[swap_proposal_id].votes.remove(sp.sender)

    # Vote to cancel an existing swap
    # This will call HEN's cancel() if everyone votes
    # params.swap_id - The swap to cancel, must be a valid swap_id that the contract owns
    @sp.entry_point
    def vote_cancel_swap(self, params):
        sp.if ~self.data.owners.contains(sp.sender):
            sp.failwith("not owner")
        
        sp.if ~self.data.locked:
            sp.failwith("fund unlocked")

        # Add to set of votes if it exists
        # Otherwise, create the set and initialize
        sp.if self.data.cancel_swap_proposals.contains(params.swap_id):
            self.data.cancel_swap_proposals[params.swap_id].votes.add(sp.sender)
        sp.else:
            self.data.cancel_swap_proposals[params.swap_id] = sp.record(votes=sp.set([sp.sender]), passed=False)

        sp.if sp.len(self.data.cancel_swap_proposals[params.swap_id].votes) == self.data.numOwners:
            self.hen_cancel_swap(params.swap_id)
    
    # Undo your vote to cancel an existing swap
    @sp.entry_point
    def undo_vote_cancel_swap(self, params):
        self.data.cancel_swap_proposals[params.swap_id].votes.remove(sp.sender)

    ### HEN Contract Functions ###    
    def hen_collect(self, swap_id):
        # TODO get the price of the objkt using the swap_id
        # OR, the caller is responsible for getting the price and passing as an arg
        c = sp.contract(sp.TPair(sp.TNat, sp.TNat), self.data.hen_address, entry_point = "collect").open_some()
        sp.transfer(sp.pair(1, swap_id), sp.mutez(0), c)

    def hen_swap(self, swap_proposal_id):
        # Check that the swap exists
        sp.if ~self.data.swap_proposals.contains(swap_proposal_id):
            sp.failwith("swap doesn't exist")

        # Get swap info
        swap_info = self.data.swap_proposals[swap_proposal_id]
        
        # Call into HEN contract
        c = sp.contract(sp.TPair(sp.TNat, sp.TPair(sp.TNat, sp.TMutez)), self.data.hen_address, entry_point = "swap").open_some()
        sp.transfer(sp.pair(swap_info.objkt_amount, sp.pair(swap_info.objkt_id, swap_info.xtz_per_objkt)), sp.mutez(0), c)

    def hen_cancel_swap(self, swap_id):
        c = sp.contract(sp.TNat, self.data.hen_address, entry_point = "cancel_swap").open_some()
        sp.transfer(swap_id, sp.mutez(0), c)

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
        scenario.verify(c1.data.total_contributed == sp.mutez(15))
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

    @sp.add_test(name = "Test_Lock")
    def test():
        c1 = HENDao([sp.address("tz1owner1"), sp.address("tz1owner2")])
        scenario = sp.test_scenario()
        scenario.h1("Test Lock")
        scenario += c1
        user1 = sp.address("tz1owner1")
        user2 = sp.address("tz1owner2")
        
        scenario.h2("Contract starts unlocked")
        scenario.verify(c1.data.locked == False)

        scenario.h2("Users can call lock")
        c1.vote_lock().run(sender=user1)

        scenario.h2("Contract is unlocked when everyone locks")
        c1.vote_lock().run(sender=user2)
        scenario.verify(c1.data.locked == True)
        # Still should stay closed
        scenario.verify(c1.data.closed == False)
    
    @sp.add_test(name = "Test_Swap")
    def test():
        c1 = HENDao([sp.address("tz1owner1"), sp.address("tz1owner2")])
        scenario = sp.test_scenario()
        scenario.h1("Test Propose Swap")
        scenario += c1
        user1 = sp.address("tz1owner1")
        user2 = sp.address("tz1owner2")

        scenario.h2("Users can call propose swap")
        c1.vote_lock().run(sender=user1)
        c1.vote_lock().run(sender=user2)
        c1.propose_swap(objkt_amount=sp.nat(1), objkt_id=sp.nat(123), xtz_per_objkt=sp.mutez(10000)).run(sender=user1)
        c1.propose_swap(objkt_amount=sp.nat(1), objkt_id=sp.nat(456), xtz_per_objkt=sp.mutez(100)).run(sender=user2)
        scenario.verify(c1.data.swap_proposals[0].passed == False)
        scenario.verify(c1.data.swap_proposals[1].passed == False)
        
        scenario.h2("All votes for a swap")
        # Vote to pass the proposals
        c1.vote_swap(0).run(sender=user2)
        c1.vote_swap(1).run(sender=user1)
        
        # Test double vote fails
        c1.vote_swap(0).run(sender=user2, valid=False)

        # Verify that num votes is valid
        scenario.verify(sp.len(c1.data.swap_proposals[0].votes) == 2)
        
        # Verify that proposal is passed
        scenario.verify(c1.data.swap_proposals[0].passed == True)
        scenario.verify(c1.data.swap_proposals[1].passed == True)

    # TODO Add the initial addresses here when deploying contract
    sp.add_compilation_target("henDao", HENDao([]))
