'''
This module provides a minimal implementation of the Paxos algorithm
that is independent of the underlying messaging mechanism. These
classes implement only the essential Paxos components and omit
the practical considerations (such as durability, message
retransmissions, NACKs, etc).
'''

import collections

# In order for the Paxos algorithm to function, all proposal ids must be
# unique. A simple way to ensure this is to include the proposer's UID
# in the proposal id. This prevents the possibility of two Proposers
# from proposing different values for the same proposal ID.
#
# Python tuples are a simple mechanism that allow the proposal number
# and the UID to be combined easily and in a manner that supports
# comparison. To simplify the code, we'll use "namedtuple" instances
# from the collections module which allows us to write
# "proposal_id.number" instead of "proposal_id[0]".
#
ProposalID = collections.namedtuple('ProposalID', ['number', 'uid'])


class Messenger (object):
    def send_prepare(self, proposal_id):
        '''
        Broadcasts a Prepare message to all Acceptors
        '''

    def send_promise(self, proposer_uid, proposal_id, previous_id, accepted_value):
        '''
        Sends a Promise message to the specified Proposer
        '''

    def send_accept(self, proposal_id, proposal_value):
        '''
        Broadcasts an Accept! message to all Acceptors
        '''

    def send_accepted(self, proposal_id, accepted_value):
        '''
        Broadcasts an Accepted message to all Learners
        '''

    def on_resolution(self, proposal_id, value):
        '''
        Called when a resolution is reached
        '''


class Proposer(object):
    messenger = None
    proposer_uid = None
    quorum_size = None

    proposed_value = None
    proposal_id = None
    last_accepted_id = None
    next_proposal_number = 1
    promises_rcvd = None

    def set_proposal(self, value):
        '''
        Sets the proposal value for this node iff this node is not already aware of
        another proposal having already been accepted.
        '''
        if self.proposed_value is None:
            self.proposed_value = value

    def prepare(self):
        '''
        Sends a prepare request to all Acceptors as the first step in attempting to
        acquire leadership of the Paxos instance.
        '''
        self.promises_rcvd = set()
        self.proposal_id = ProposalID(self.next_proposal_number, self.proposer_uid)

        self.next_proposal_number += 1

        self.messenger.send_prepare(self.proposal_id)

    def recv_promise(self, from_uid, proposal_id, prev_accepted_id, prev_accepted_value):
        # TODO
        # Called when a Promise response is received from an Acceptor
        # Hints:
        #     In this area, the proposer need to ignore the message. Please consider in what cases the proposer
        #     has to ignore the message.just use 'return' in that case.
        #     Also, if the message has been already received (from_uid is the identifier), just 'return'.
        if proposal_id != self.proposal_id:
            return
        if from_uid in self.promises_rcvd:
            return

        self.promises_rcvd.add(from_uid)

        # TODO
        # Hints:
        #     Consider what if the prev_accepted_id given by the acceptor is greater than the self.last_accepted_id
        #     In this case, how should the state variables of the proposer change?

        if prev_accepted_id > self.last_accepted_id:
            self.last_accepted_id = prev_accepted_id
            if prev_accepted_value is not None:
                self.proposed_value = prev_accepted_value

        if len(self.promises_rcvd) == self.quorum_size:

            if self.proposed_value is not None:
                self.messenger.send_accept(self.proposal_id, self.proposed_value)


class Acceptor (object):

    messenger      = None
    promised_id    = None
    accepted_id    = None
    accepted_value = None

    def recv_prepare(self, from_uid, proposal_id):
        # TODO
        # Called when a Prepare message is received from a Proposer
        # Hints:
        #     You should consider both of the cases:
        #         1. the currently received proposal id is equals to previously received proposal id.
        #         2. the currently received proposal id is not equals to previously received proposal id.
        #     You should use the send_promise() method defined in messenger to send out the promise command.
        if proposal_id == self.promised_id:
            self.messenger.send_promise(from_uid, proposal_id, self.accepted_id, self.accepted_value)
        elif proposal_id > self.promised_id:
            self.promised_id = proposal_id
            self.messenger.send_promise(from_uid, proposal_id, self.accepted_id, self.accepted_value)

    def recv_accept_request(self, from_uid, proposal_id, value):
        # TODO
        # Called when an Accept! message is received from a Proposer
        # Hints:
        #     You should consider which case the acceptor should response to the propose request.
        #     You should change the inner state variable of acceptor, e.g., the promised_id, accepted_id and the accepted_value.
        #     You should use the send_accepted() method defined in messenger to send out the accept command.
        if proposal_id >= self.promised_id:
            self.promised_id = proposal_id
            self.accepted_id = proposal_id
            self.accepted_value = value
            self.messenger.send_accepted(proposal_id, self.accepted_value)


class Learner(object):
    quorum_size = None

    proposals = None  # maps proposal_id => [accept_count, retain_count, value]
    acceptors = None  # maps from_uid => last_accepted_proposal_id
    final_value = None
    final_proposal_id = None

    @property
    def complete(self):
        return self.final_proposal_id is not None

    def recv_accepted(self, from_uid, proposal_id, accepted_value):
        '''
        Called when an Accepted message is received from an acceptor
        '''
        if self.final_value is not None:
            return  # already done

        if self.proposals is None:
            self.proposals = dict()
            self.acceptors = dict()

        last_pn = self.acceptors.get(from_uid)

        if not proposal_id > last_pn:
            return  # Old message

        self.acceptors[from_uid] = proposal_id

        if last_pn is not None:
            oldp = self.proposals[last_pn]
            oldp[1] -= 1
            if oldp[1] == 0:
                del self.proposals[last_pn]

        if not proposal_id in self.proposals:
            self.proposals[proposal_id] = [0, 0, accepted_value]

        t = self.proposals[proposal_id]

        assert accepted_value == t[2], 'Value mismatch for single proposal!'

        t[0] += 1
        t[1] += 1

        if t[0] == self.quorum_size:
            self.final_value = accepted_value
            self.final_proposal_id = proposal_id
            self.proposals = None
            self.acceptors = None

            self.messenger.on_resolution(proposal_id, accepted_value)