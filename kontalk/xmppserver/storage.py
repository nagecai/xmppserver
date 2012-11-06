# -*- coding: utf-8 -*-
"""Storage modules."""
"""
  Kontalk XMPP server
  Copyright (C) 2011 Kontalk Devteam <devteam@kontalk.org>

 This program is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.

 This program is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.

 You should have received a copy of the GNU General Public License
 along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""


from twisted.enterprise import adbapi
from twisted.words.protocols.jabber import jid

import base64
import util

dbpool = None

def init(config):
    global dbpool
    dbpool = adbapi.ConnectionPool(config['dbmodule'], host=config['host'], port=config['port'],
        user=config['user'], passwd=config['password'], db=config['dbname'])


""" interfaces """


class StanzaStorage():
    """Stanza storage system."""

    def store(self, stanza):
        """Store a stanza."""
        pass

    def get_by_id(self, stanzaId):
        """Retrieve a stanza by id."""
        pass

    def get_by_sender(self, sender):
        """Retrieve stanzas by sender."""
        pass

    def get_by_recipient(self, recipient):
        """Retrieve stanzas by recipient."""
        pass


class PresenceStorage():
    """Presence cache storage."""

    def get(self, user_jid):
        """Retrieve info about a user."""
        pass

    def presence(self, stanza):
        """Persist a presence."""
        pass

    def touch(self, user_jid):
        """Update last seen timestamp of a user."""
        pass


class NetworkStorage():
    """Network info storage."""

    def get_list(self):
        """Retrieve the list of servers in this network."""
        pass



""" implementations """


class MySQLStanzaStorage(StanzaStorage):

    def store(self, stanza):
        pass

    def get_by_id(self, stanzaId):
        global dbpool
        def _translate(tx, stanzaId):
            tx.execute('SELECT content, timestamp FROM stanzas WHERE id = ?', (stanzaId, ))
            return tx.fetchone()
        return dbpool.runInteraction(_translate, stanzaId)

    def get_by_sender(self, sender):
        # TODO
        #global dbpool
        #return dbpool.runQuery('SELECT id, recipient, content, timestamp FROM stanzas WHERE sender = ?', sender)
        pass

    def get_by_recipient(self, recipient):
        pass

class MySQLNetworkStorage(NetworkStorage):

    def get_list(self):
        global dbpool
        def _translate(tx):
            out = {}
            tx.execute('SELECT fingerprint, host, s2s_port FROM servers')
            data = tx.fetchall()
            for row in data:
                fp = str(row[0])
                out[fp] = {
                    'host' : str(row[1]),
                    's2s' : int(row[2]),
                }
            return out
        return dbpool.runInteraction(_translate)

class MySQLPresenceStorage(PresenceStorage):

    def get(self, user_jid):
        def _fetchone(tx, query, args):
            tx.execute(query, args)
            data = tx.fetchone()
            return {
                'timestamp': data[0],
                'status': data[1],
                'show': data[2]
            }
        def _fetchall(tx, query, args):
            tx.execute(query, args)
            data = tx.fetchall()
            out = []
            for d in data:
                out.append({
                    'timestamp': d[0],
                    'status': d[1],
                    'show': d[2]
                })
            return out

        userid = util.jid_to_userid(user_jid)
        if user_jid.resource:
            interaction = _fetchone
            query = 'SELECT `timestamp`, `status`, `show` FROM presence WHERE userid = ?'
            args = (userid, )
        else:
            interaction = _fetchall
            query = 'SELECT `timestamp`, `status`, `show` FROM presence WHERE SUBSTR(userid, 1, 40) = ? AND `timestamp` = (SELECT MAX(`timestamp`) FROM presence WHERE SUBSTR(userid, 1, 40) = ?)'
            args = (userid, userid)

        return dbpool.runInteraction(interaction, query, args)

    def presence(self, stanza):
        global dbpool
        sender = jid.JID(stanza['from'])
        userid = util.jid_to_userid(sender)

        def encode_not_null(val):
            if val is not None:
                return base64.b64encode(val.__str__().encode('utf-8'))
            else:
                return None

        values = (userid, encode_not_null(stanza.status), util.str_none(stanza.show))
        dbpool.runOperation('REPLACE INTO presence VALUES(?, NOW(), ?, ?)', values)

    def touch(self, user_jid):
        global dbpool
        userid = util.jid_to_userid(user_jid)
        dbpool.runOperation('UPDATE presence SET timestamp = NOW() WHERE userid = ?', (userid, ))