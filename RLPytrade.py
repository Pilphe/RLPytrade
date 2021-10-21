import requests
import json
import time
import threading
import signal
import sys
import configparser
import winsound
from datetime import datetime
from SimpleWebSocketServer import SimpleWebSocketServer, WebSocket

CONFIG_FILE = 'config.ini'
CONFIG = configparser.ConfigParser()
CONFIG.read(CONFIG_FILE)

class TokenAuth():
    def __init__(self, config_section):
        self._cfg = config_section
        self._token = {
            'access_token': CONFIG[self._cfg]['access_token'],
            'refresh_token': CONFIG[self._cfg]['refresh_token'],
            'expires_at': CONFIG[self._cfg]['expires_at']
        }
        self._s = requests.Session()
        self._s.headers.update({
            'User-Agent': CONFIG['rltp']['ua'],
            'Authorization': f"Bearer {self._token['access_token']}",
            'Accept': None
        })
        #self._s.proxies = {'https':'http://192.168.1.60:8082'}
        #self._s.verify = 'root_ca.cer'
        
    def _ensureTokenValidity(self):
        refresh = False
        if int(self._token['expires_at']) < int(time.time()):
            self._refreshToken()
            refresh = True
        return refresh

    def _refreshToken(self):
        self._s.headers['Authorization'] = None
        r = self._s.send(self._prepareTokenRequest())
        if r.status_code == 200:
            self._token |= r.json()
            self._token['expires_at'] = str(int(time.time()) + int(self._token['expires_in']))
            self._s.headers['Authorization'] = f"Bearer {self._token['access_token']}"
            self._updateConfig()
        else:
            raise ValueError(f"Failed to refresh {self._cfg} token: {r.text}")
            
    def _updateConfig(self):
        CONFIG[self._cfg]['access_token'] = self._token['access_token']
        CONFIG[self._cfg]['refresh_token'] = self._token['refresh_token']
        CONFIG[self._cfg]['expires_at'] = self._token['expires_at']
        with open(CONFIG_FILE, 'w') as f:
            CONFIG.write(f)
            
    def _prepareTokenRequest(self):
        pass

class PSN(TokenAuth):
    def __init__(self):
        TokenAuth.__init__(self, 'psn')
        
    def _prepareTokenRequest(self):
        return self._s.prepare_request(
            requests.Request(
                'POST',
                CONFIG['psn']['token_url'],
                data={
                    'app_context': 'inapp_ios',
                    'client_id': CONFIG['psn']['client_id'],
                    'client_secret': CONFIG['psn']['client_secret'],
                    'refresh_token': CONFIG['psn']['refresh_token'],
                    'duid': CONFIG['psn']['duid'],
                    'grant_type': 'refresh_token',
                    'scope': 'kamaji:get_players_met kamaji:get_account_hash kamaji:activity_feed_submit_feed_story kamaji:activity_feed_internal_feed_submit_story kamaji:activity_feed_get_news_feed kamaji:communities kamaji:game_list kamaji:ugc:distributor oauth:manage_device_usercodes psn:sceapp user:account.profile.get user:account.attributes.validate user:account.settings.privacy.get kamaji:activity_feed_set_feed_privacy kamaji:satchel kamaji:satchel_delete user:account.profile.update'
                },
            )
        )
        
    def sendFriendRequest(self, psn_id):
        if self._ensureTokenValidity():
            print("(PSN) Token renewed successfully")
        r = self._s.post(f"{CONFIG['psn']['send_url']}/{psn_id}", json={})
        if r.status_code == 204:
            print("(PSN) Friend request sent")
        else:
            print(f"(PSN) +++ ERROR +++ Failed to send friend request to {psn_id}")

class RLTPAPI():
    def __init__(self, user):
        self.cfg = 'rltp'
        self.tid_key = "_id"
        self.user = user
        self.rtrades = CONFIG[self.cfg][f'rtrades_{user}'].split()
        self.btrades = CONFIG[self.cfg][f'btrades_{user}'].split()
        self._username = CONFIG[self.cfg][f'username_{user}']
        self._s = requests.Session()
        self._s.headers.update({
            'User-Agent': CONFIG[self.cfg]['ua'],
            'Accept': None,
            'lang': CONFIG[self.cfg]['lang'],
            'username': self._username,
            'token': CONFIG[self.cfg][f'token_{user}'],
            'mobilekey': CONFIG[self.cfg]['mobile_key']
        })
        self._last_createdtime = datetime.strptime('1970-01-01', '%Y-%m-%d')
        self._last_updatedtime = datetime.strptime('1970-01-01', '%Y-%m-%d')
        #self._s.proxies = {'https':'http://192.168.1.60:8082'}
        #self._s.verify = 'root_ca.cer'
    
    def getNewTrades(self, filters=None):
        global total_rltp_trades
        new_trades = None
        r = self._s.get(f"{CONFIG[self.cfg]['url']}{CONFIG[self.cfg]['trades_endpoint']}", params=filters)
        if r.status_code == 200:
            self._updateCacheHeader(r.headers)
            jtrades = r.json()
            all_trades = []
            new_trades = [x for x in jtrades if (self._createdTimeToObj(x) > self._last_createdtime)]
            updated_trades = [x for x in jtrades if (self._updatedTimeToObj(x) > self._last_updatedtime)]
            if new_trades or updated_trades:
                if updated_trades and new_trades:
                    for ntrade in new_trades:
                        for utrade in updated_trades:
                            if ntrade['_id'] == utrade['_id']:
                                del utrade
                                break
                    self._last_createdtime = self._createdTimeToObj(max(new_trades, key=self._createdTimeToObj))
                    if updated_trades:
                        self._last_updatedtime = self._updatedTimeToObj(max(updated_trades, key=self._updatedTimeToObj))
                all_trades = (new_trades + updated_trades)
                total_rltp_trades += len(all_trades)
            print(f"({self.__class__.__name__}) Trades since last GET: {len(new_trades)} new, {len(updated_trades)} bumped, {len(all_trades)} in total")
        elif r.status_code != 304:
            print(f"({self.__class__.__name__}) +++ ERROR +++ Failed to get trades ({r.status_code}):\n{r.text}")
        return new_trades
    
    def getMyTrades(self, clear=False):
        #print(f"({self.__class__.__name__}) +++ {self.getMyTrades.__name__}: IN +++")
        trades = None
        params = {
            'rltpusername': f"{self._username}"
        }
        r = self._s.get(f"{CONFIG[self.cfg]['url']}{CONFIG[self.cfg]['trades_endpoint']}", params=params)
        if r.status_code == 200:
            trades = r.json()
            if clear:
                for trade in trades:
                    del (
                        trade['userId'],
                        trade['__v'],
                        trade['lastupdatedtime'],
                        trade['createdtime'],
                        trade['status'],
                        trade['isBookmarked'],
                        trade['lastUpdatedTimestamp']
                    )
        else:
            print(f"({self.__class__.__name__}) +++ ERROR +++ Failed to get owned trades ({r.status_code}):\n{r.text}")
        #print(f"({self.__class__.__name__}) +++ {self.getMyTrades.__name__}: OUT +++")
        return trades
        
    def bumpTrade(self, trade):
        bump = False
        r = self._s.put(f"{CONFIG[self.cfg]['url']}{CONFIG[self.cfg]['trades_endpoint']}", json=trade)
        if r.status_code != 200:
            print(f"({self.__class__.__name__}) +++ ERROR +++ Failed to bump trade ({r.status_code}):\n{r.text}")
        else:
            bump = True
            print(f"({self.__class__.__name__}) Trade bumped successfully")
        return bump
    
    def createTrade(self, trade):
        #print(f"({self.__class__.__name__}) +++ {self.createTrade.__name__}: IN +++")
        id = None
        trade.pop('_id')
        r = self._s.post(f"{CONFIG[self.cfg]['url']}{CONFIG[self.cfg]['trades_endpoint']}", json=trade)
        if r.status_code != 200:
            print(f"({self.__class__.__name__}) +++ ERROR +++ Failed to create trade ({r.status_code}):\n{r.text}")
            if not shutdown.is_set():
                print(f"({self.__class__.__name__}) Retrying to create trade...")
                time.sleep(4)
                return self.createTrade(trade)
        else:
            id = r.json()['_id']
            print(f"({self.__class__.__name__}) Trade created successfully")
        #print(f"({self.__class__.__name__}) +++ {self.createTrade.__name__}: OUT +++")
        return id
    
    def deleteTrade(self, trade):
        #print(f"({self.__class__.__name__}) +++ {self.deleteTrade.__name__}: IN +++")
        delete = False
        params = {
            'rltpusername': f"{self._username}",
            '_id': trade['_id']
        }
        r = self._s.delete(f"{CONFIG[self.cfg]['url']}{CONFIG[self.cfg]['trades_endpoint']}", params=params)
        if r.status_code != 200:
            print(f"({self.__class__.__name__}) +++ ERROR +++ Failed to delete trade ({r.status_code}):\n{r.text}")
        else:
            delete = True
            print(f"({self.__class__.__name__}) Trade deleted successfully")
        #print(f"({self.__class__.__name__}) +++ {self.deleteTrade.__name__}: OUT +++")
        return delete
    
    def _updateCacheHeader(self, headers):
        if 'ETag' in headers:
            self._s.headers['If-None-Match'] = headers['ETag']
            
    def _createdTimeToObj(self, trade):
        return datetime.strptime(trade['createdtime'], '%Y-%m-%dT%H:%M:%S.%fZ')
        
    def _updatedTimeToObj(self, trade):
        return datetime.strptime(trade['lastupdatedtime'], '%Y-%m-%dT%H:%M:%S.%fZ')

class RLGAPI():
    def __init__(self, user):
        self.cfg = 'rlg'
        self.tid_key = "alias"
        self.user = user
        self.rtrades = CONFIG[self.cfg][f'rtrades_{user}'].split()
        self.btrades = CONFIG[self.cfg][f'btrades_{user}'].split()
        self._s = requests.Session()
        self._s.headers.update({
            'Accept': 'application/json, text/plain, */*',
            'authkey': CONFIG[self.cfg][f'auth_key_{user}'],
            'rng_no': CONFIG[self.cfg][f'rn_{user}'],
            'rlg-user-agent': CONFIG[self.cfg]['rlgua'],
            'language': CONFIG[self.cfg]['lang'],
            'User-Agent': CONFIG[self.cfg]['ua']
        })
        self._s.proxies = {'https':'http://192.168.1.60:8082'}
        self._s.verify = 'root_ca.cer'
        self._login()
        
    def _login(self):
        login = False
        files = {
            'submit': (None, '1'),
            'email': (None, CONFIG[self.cfg][f'email_{self.user}']),
            'password': (None, CONFIG[self.cfg][f'password_{self.user}'])
        }
        r = self._s.post(f"{CONFIG[self.cfg]['url']}{CONFIG[self.cfg]['login_endpoint']}", files=files)
        if r.status_code != 200:
            print(f"(RLG) +++ ERROR +++ Login failed ({r.status_code}):\n{r.text}")
        else:
            login = True
            print("(RLG) login success")
        return login
        
    def getMyTrades(self, clear=False):
        trades = None
        retry = False
        params = {
            'userId': CONFIG[self.cfg][f'uid_{self.user}']
        }
        r = self._s.get(f"{CONFIG[self.cfg]['url']}{CONFIG[self.cfg]['user_trades_endpoint']}", params=params)
        if r.status_code != 200:
            retry = True
        else:
            try:
                trades = r.json()
            except (json.decoder.JSONDecodeError):
                retry = True
            else:
                if clear:
                    for trade in trades:
                        items_tuple = (json.loads(trade['items'], parse_int=str), json.loads(trade['tradeitems'], parse_int=str))
                        for items in items_tuple:
                            for item in items:
                                del (
                                    item['platforms'],
                                    item['order']
                                )
                                if 'rarity' in item and item['rarity'] == "0":
                                    del item['rarity']
                        trade['items'] = json.dumps(items_tuple[0], separators=(',', ':'))
                        trade['tradeitems'] = json.dumps(items_tuple[1], separators=(',', ':'))
        if retry:
            print(f"(RLG) +++ ERROR +++ Failed to get owned trades ({r.status_code}):\n{r.text}")
            if not shutdown.is_set():
                print("(RLG) Retrying to get owned trade...")
                time.sleep(3)
                return self.getMyTrades(clear)
        return trades
    
    #unused
    def getTrade(self, id, clear=False):
        params = {
            'alias': id
        }
        r = self._s.get(f"{CONFIG[self.cfg]['url']}{CONFIG[self.cfg]['get_trade_endpoint']}", params=params)
    
    def createTrade(self, trade):
        id = None
        retry = False
        files = {
            'note': (None, trade['note']),
            'ownerItems': (None, trade['items']),
            'tradeItems': (None, trade['tradeitems']),
            'platform': (None, str(trade['platform'])),
            'additionalPlatforms': (None, json.dumps(trade['additionalPlatforms']))
        }
        r = self._s.post(f"{CONFIG[self.cfg]['url']}{CONFIG[self.cfg]['add_trade_endpoint']}", files=files)
        if r.status_code != 200 and (r.status_code != 400 or (r.status_code == 400 and "too quickly" in r.text)):
            retry = True
        else:
            try:
                id = r.json()['data']
            except (json.decoder.JSONDecodeError):
                retry = True
            else:
                print("(RLG) Trade created successfully")
        if retry:
            print(f"(RLG) +++ ERROR +++ Failed to create trade ({r.status_code}):\n{r.text}")
            if not shutdown.is_set():
                print("(RLG) Retrying to create trade...")
                time.sleep(10)
                return self.createTrade(trade)
        return id
        
    def deleteTrade(self, trade):
        delete = False
        params = {
            'trade': trade['alias']
        }
        r = self._s.get(f"{CONFIG[self.cfg]['url']}{CONFIG[self.cfg]['disable_trade_endpoint']}", params=params)
        if r.status_code != 200:
            print(f"(RLG) +++ ERROR +++ Failed to delete trade ({r.status_code}):\n{r.text}")
        else:
            delete = True
            print("(RLG) Trade deleted successfully")
        return delete
        
    def bumpTrade(self, trade):
        bump = False
        params = {
            'alias': trade['alias']
        }
        r = self._s.get(f"{CONFIG[self.cfg]['url']}{CONFIG[self.cfg]['bump_endpoint']}", params=params)
        if r.status_code == 200:
            bump = True
            print("(RLG) Trade bumped successfully")
        else:
            print(f"(RLG) +++ ERROR +++ Failed to bump trade ({r.status_code}):\n{r.text}")
        return bump

class RLTPFCM(TokenAuth):
    def __init__(self):
        TokenAuth.__init__(self, 'fcm')
        self._s.headers['Content-Type'] = 'application/json; charset=utf-8'
    
    def _prepareTokenRequest(self):
        return self._s.prepare_request(
            requests.Request(
                'POST',
                CONFIG['fcm']['token_url'],
                params={
                    'key': CONFIG['fcm']['key']
                },
                json={
                    'grantType': 'refresh_token',
                    'refreshToken': self._token['refresh_token']
                }
            )
         )
    
    def sendMessage(self, data):
        if self._ensureTokenValidity():
            print("(RLTP FCM) Token renewed successfully")
        response = self._s.post(CONFIG['fcm']['send_url'], data=data)
        if response.status_code != 200:
            print(f"(RLTP FCM) +++ ERROR +++ Failed to send message: {data}")
            return False
        return True
        

class RLTPWebSocket(WebSocket):
    def __init__(self, server, sock, address):
        WebSocket.__init__(self, server, sock, address)
        # requires browser to be connected, maybe change this later?
        self.fcm = RLTPFCM()
        self.psn = PSN()

    def handleConnected(self):
        global browser_connected, browser_ws
        browser_connected = True
        browser_ws = self

    def handleClose(self):
        global browser_connected, browser_ws
        browser_connected = False
        browser_ws = None

    def handleMessage(self):
        self.fcm.sendMessage (self.data)

def run_ws_server():
    global ws_server
    ws_server = SimpleWebSocketServer("127.0.0.1", 5455, RLTPWebSocket)
    while not shutdown.is_set():
        ws_server.serveonce()
    ws_server.close()

def item_dict_to_string(item):
    s = ""
    if item['color'] != 'None':
        s += f"{item['color']} "
    if item['certification'] != 'None':
        s += f"{item['certification']} "
    s += item['name']
    if item['isblueprint']:
        s += " Blueprint"
    return s

def items_list_to_string(items):
    s = ""
    for item in items:
        item_s = ""
        if item['quantity'] > 1:
            item_s += f"{str(item['quantity'])}x"
        item_s += item_dict_to_string(item)
        if 'highlight' in item:
            item_s = f"<span class=\"highlight\">{item_s}</span>"
        s += f"{item_s}, "
    return s[:-2] # .lower() ?

def human_readable_time(time):
    return (datetime.strptime(time, '%Y-%m-%dT%H:%M:%S.%fZ')).strftime("%d/%m/%Y\n%H:%M:%S")

def trades_list_to_html(trades):
    html = ""
    for trade in trades:
        html += (
            "<tr class=\"new_row{}\">".format(" auto" if 'auto' in trade else "")
            + f"<td><img class=\"platform_logo\" src=\"images/{trade['platform']}.png\">{trade['platformname']}</td>"
            f"<td>{items_list_to_string(trade['have'])}</td>"
            f"<td>{items_list_to_string(trade['want'])}</td>"
            "<td class=\"icons\">"
            # Notes aren't sanitized, injection can happen !
            + "<span class=\"icon cursor_default{}>&#x1F4DD;</span>".format(f"\" title=\"{trade['notes']}\"" if trade['notes'] else " disabled\"")
            + f"<span class=\"icon cursor_default\" title=\"{human_readable_time(trade['createdtime'])}\">&#x1F551;</span>"
            f"<span class=\"icon cursor_pointer\" data-uid=\"{trade['userId']}\" data-uname=\"{trade['rltpusername']}\" data-pname=\"{trade['platformname']}\" onclick=\"sendMessage(this)\">&#x1F4AC;</span>"
            "</td>"
            "</tr>"
        )
    return html


'''
# Fennec automatic messages
auto_msg_checked = False (avoid two messages for same trade)
if item['name'] == wanted[0] and not auto_msg_checked:
    auto_msg_checked = True
    auto_message(trade, wanted[0])
 '''

# (<name>, <color>, <is blueprint?>, <platform>)
# None = accept all
wanted = [
    ("Goop", None, True, None),
    ("Anodized Pearl", None, True, None),
    ("Blender", None, True, None),
    ("Pixel Fire", None, True, None),
    ("Proton", None, True, None),
    ("Octane: MG-88", None, True, None),
    ("Spiralis R2", None, True, None),
    ("Imperator DT5", None, True, None),
    ("Hiro", None, True, None),
    ("Fractal Fire", None, True, None),
    ("Equalizer", None, True, None),
    ("Hikari P5", None, True, None),
    ("Dynamo", None, True, None),
    ("Reactor", None, True, None),
    ("Gernot", None, True, None),
    ("Raijin", None, True, None),
    ("Zomba", ("Titanium White",), True, None),
    ("Twinzer", ("Black",), False, None),
    #("Dust Cloud", ("Titanium White",), False, None),
    #("Fennec", None, None, None),
    #("Maverick GXT", None, None, None),
    ("Blueprint II", None, None, None),
    ("Blueprint", None, None, None),
    #("Hustle Brows", None, None, None),
    #("Maverick G1", None, False, None)
    #("Fusion", ("Titanium White",), False, None),
    #("Illuminata", ("Titanium White",), None, None),
    #("Octane", ("Titanium White", "Crimson"), False, None),
    #("Dominus", ("Titanium White", "Black", "Grey", "Crimson", "Pink", "Cobalt", "Sky Blue", "Burnt Sienna", "Saffron", "Lime", "Forest Green", "Orange", "Purple"), False, None),
    #("Apex", None, False, None),
    #("Octane: Dune Racer", None, False, None),
    #("Octane: CRL Northern", ("Black", "Titanium White", "Grey", "Crimson"), False, None),
    #("Octane: RLCS", ("Black", "Titanium White"), False, None),
    #("Dominus: CRL Southern", ("Black", "Titanium White", "Grey", "Crimson"), False, None),
    #("Helios", ("Black", "Titanium White", "Grey", "Crimson", "Sky Blue"), False, None),
    #("Dominus: RLCS", ("Black", "Titanium White"), False, None),
    #("Octane: RLCS X", ("Black", "Titanium White"), False, None),
    #("Octane: Nice Shot", ("Titanium White", "Crimson"), False, None),
    #("Fennec", ("Titanium White",), None, None),
    #("Mainframe", ("Titanium White",), None, None),
    #("Dieci", ("Black", "Titanium White"), False, None),
    #("EQ", ("Black", "Titanium White"), False, None),
    #("Veloce", ("Black",), False, None),
    #("Tunica", ("Black",), False, None),
    #("Hephaestus", ("Black", "Titanium White"), False, None),
    #("Aero Mage", ("Black", "Titanium White"), False, None),
    #("Razzle", ("Black", "Titanium White", "Grey"), False, None),
    #("Metalstar", ("Black", "Titanium White", "Crimson"), False, None),
    #("Dynamo", ("Crimson",), False, None),
    #("Draco", ("Titanium White", "Crimson"), None, None),
    #("Emerald", ("Titanium White", "Black", "Grey", "Crimson", "Pink", "Cobalt", "Sky Blue", "Burnt Sienna", "Saffron", "Lime", "Forest Green", "Orange", "Purple"), False, None),
    #("Reaper", ("Titanium White", "Black"), None, None),
    #("Decennium", ("Titanium White", "Black", "Crimson"), False, None),
    #("Vampire Bat", ("Titanium White", "Black"), None, None),
    #("Dueling Dragons", None, None, None),
    #("Cutter: Inverted", ("Titanium White",), False, "PS4")
]
def is_interesting(trade, check_my_items=True):
    if trade['userId'] == CONFIG['rltp']['uid_nev'] or trade['userId'] == CONFIG['rltp']['uid_choon']:
        return False
    notes = trade['notes'].lower()
    if (
        'help' in notes
        or 'dump' in notes
        or 'trash' in notes
        or 'free' in notes
        or 'junk' in notes
        or 'stop' in notes
        or 'quit' in notes
        or 'gratuit' in notes
        or 'donne' in notes
        or 'aide' in notes
        or 'cadeau' in notes
        or 'gift' in notes
        or 'leav' in notes
    ):
        winsound.PlaySound("Notification.Looping.Alarm", winsound.SND_ALIAS | winsound.SND_ASYNC)
        return True
    is_it = False
    if check_my_items:
        for item in trade['want']:
            if item['name'] == "Trash It!":
                winsound.PlaySound("Notification.Looping.Alarm", winsound.SND_ALIAS | winsound.SND_ASYNC)
                return True
            item_str = item_dict_to_string(item)
            if item_str in my_items:
                if not is_it:
                    is_it = True
                item['highlight'] = True
    #auto_msg_checked = False
    for item in trade['have']:
        '''
        if item['name'] == wanted[17][0] and not auto_msg_checked:
            auto_msg_checked = True
            auto_message(trade, wanted[17][0])
        '''
        if item['name'] == "Trash It!":
            winsound.PlaySound("Notification.Looping.Alarm", winsound.SND_ALIAS | winsound.SND_ASYNC)
            return True
        for witem in wanted:
            if (
                item['name'] != witem[0]
                or (witem[1] != None and item['color'] not in witem[1])
                or (witem[2] != None and witem[2] != item['isblueprint'])
                or (witem[3] != None and witem[3] != trade['platform'])
            ):
                continue
            if not is_it:
                is_it = True
            item['highlight'] = True
            break
    return is_it

def build_fcm_message(trade, have, want):
    data = {
        'data': {
            'members': [
                {
                    'uid': CONFIG['rltp']['uid_nev'],
                    'username': CONFIG['rltp']['username_nev']
                },
                {
                    'uid': trade['userId'],
                    'username': trade['rltpusername']
                }
            ],
            'body': f"hey i give you {want['quantity']}cr for {item_dict_to_string(have).lower()}"
        }
    }
    return json.dumps(data)

def auto_message(trade, wanted):
    if len(trade['have']) == len(trade['want']):
        for have, want in zip(trade['have'], trade['want']):
            if not have or not want or have['name'] != wanted:
                continue
            if (want['name'] == "Credits" and want['quantity'] > 1
                and ((have['isblueprint'] and want['quantity'] <= 150)
                    or (not have['isblueprint'] and want['quantity'] <= 650))):
                if browser_ws.fcm.sendMessage(build_fcm_message(trade, have, want)):
                    if trade['platform'] == "PS4":
                        browser_ws.psn.sendFriendRequest(trade['platformname'])
                    print(f"(RLTP) Auto message sent to {trade['rltpusername']}\nNotes: {trade['notes']}\n")
                    winsound.PlaySound("Notification.Looping.Alarm2", winsound.SND_ALIAS | winsound.SND_ASYNC)
                    trade['auto'] = True
                break
                

def scrape_loop(api):
    delay = 4
    filters = {
        'platform[0]': 'PS4',
        'platform[1]': 'PC'
    }
    while not shutdown.is_set():
        trades = api.getNewTrades(filters)
        if trades:
            itrades = [x for x in trades if is_interesting(x)]
            if browser_connected and itrades:
                browser_ws.sendMessage(trades_list_to_html(itrades))
        shutdown.wait(delay)

def items_list_to_cpp_map():
    headers = {
        'Connection': 'Keep-Alive',
        'User-Agent': 'okhttp/3.12.1'
    }
    r = requests.get(f"{CONFIG['rltp']['url']}{CONFIG['rltp']['items_endpoint']}", headers=headers)
    if (r.status_code == 200):
        with open('map.txt', 'w') as f:
            for item in sorted(r.json(), key=lambda x: x['rlId']):
                f.write(f"\t\t{{{str(item['rlId'])}, \"{item['name']}\"}},\n")
        print("Items mapping success")
    else:
        print("+++ ERROR +++ Items mapping failure")

def trade_recreator(api, loop_delay, create_delay, id=None):
    global total_rltp_trades
    if id != None:
        shutdown.wait(id * 11)
    while not shutdown.is_set():
        if (type(api) is RLTPAPI):
            print(f"(RLTP) Total trades before bump: {total_rltp_trades}")
            total_rltp_trades = 0
        trades = api.getMyTrades(clear=True)
        if trades:
            if id != None:
                rtrades = [x for x in trades if x[api.tid_key] == api.rtrades[id]]
            else:
                rtrades = [x for x in trades if x[api.tid_key] not in api.btrades]
            if rtrades:
                total = len(rtrades)
                for i, trade in enumerate(rtrades, start=1):
                    print(f"({api.__class__.__name__}) Trade recreation {i}/{total}")
                    if api.deleteTrade(trade):
                        time.sleep(2)
                        tid = api.createTrade(trade)
                        if id != None and tid:
                            api.rtrades[id] = tid
                            CONFIG[api.cfg][f'rtrades_{api.user}'] = " ".join(api.rtrades)
                            with open(CONFIG_FILE, 'w') as f:
                                CONFIG.write(f)
                        time.sleep(create_delay)
        shutdown.wait(loop_delay)
        
def trade_bumper(api, delay):
    to_wait = delay - (int(time.time()) - int(CONFIG[api.cfg][f'last_bump_{api.user}']))
    if to_wait > 0:
        shutdown.wait(to_wait)
    while not shutdown.is_set():
        trades = api.getMyTrades(clear=True)
        if trades:
            btrades = [x for x in trades if x[api.tid_key] in api.btrades]
            if btrades:
                total = len(btrades)
                for i, trade in enumerate(btrades, start=1):
                    print(f"({api.__class__.__name__}) Trade bump {i}/{total}")
                    api.bumpTrade(trade)
                CONFIG[api.cfg][f'last_bump_{api.user}'] = str(int(time.time()))
                with open(CONFIG_FILE, 'w') as f:
                    CONFIG.write(f)
        shutdown.wait(delay)

def main():
    global shutdown
    print("Welcome to RL Trading Bot! ;)")

    #items_list_to_cpp_map()

    shutdown = threading.Event()

    nev_rltp = RLTPAPI('nev')
    #nev_rlg = RLGAPI('nev')

    #choon_rlg = RLGAPI('choon')
    #choon_rltp = RLTPAPI('choon')

    #sam_rltp = RLTPAPI('sam')

    ws_thread = threading.Thread(target=run_ws_server)
    #nev_rltp_recreate_thread = threading.Thread(target=trade_recreator, args=(nev_rltp, 75, 2, 0))
    #nev_rlg_recreate_thread = threading.Thread(target=trade_recreator, args=(nev_rlg, 300, 10, 0))
    #nev_rltp_recreate_thread2 = threading.Thread(target=trade_recreator, args=(nev_rltp, 200, 2, 1))
    #nev_rlg_recreate_thread2 = threading.Thread(target=trade_recreator, args=(nev_rlg, 215, 10, 1))
    #nev_rlg_recreate_thread3 = threading.Thread(target=trade_recreator, args=(nev_rlg, 440, 10, 2))
    #nev_rltp_bump_thread = threading.Thread(target=trade_bumper, args=(nev_rltp, 600))
    #nev_rlg_bump_thread = threading.Thread(target=trade_bumper, args=(nev_rlg, 900))
    #choon_rlg_recreate_thread = threading.Thread(target=trade_recreator, args=(choon_rlg, 300, 0))
    #choon_rltp_bump_thread = threading.Thread(target=trade_bumper, args=(choon_rltp, 600))
    #choon_rlg_bump_thread = threading.Thread(target=trade_bumper, args=(choon_rlg, 900))
    #sam_rltp_bump_thread = threading.Thread(target=trade_bumper, args=(sam_rltp, 600))
    #sam_rltp_recreate_thread = threading.Thread(target=trade_recreator, args=(sam_rltp, 100, 2, 0))
    #sam_rltp_recreate_thread2 = threading.Thread(target=trade_recreator, args=(sam_rltp, 240, 2, 1))
    
    ws_thread.start()
    #nev_rltp_recreate_thread.start()
    #nev_rlg_recreate_thread.start()
    #nev_rltp_recreate_thread2.start()
    #nev_rlg_recreate_thread2.start()
    #nev_rlg_recreate_thread3.start()
    #nev_rltp_bump_thread.start()
    #nev_rlg_bump_thread.start()
    #choon_rlg_recreate_thread.start()
    #choon_rltp_bump_thread.start()
    #choon_rlg_bump_thread.start()
    #sam_rltp_bump_thread.start()
    #sam_rltp_recreate_thread.start()
    #sam_rltp_recreate_thread2.start()
    
    scrape_loop(nev_rltp)
    
    ws_thread.join()
    #nev_rltp_recreate_thread.join()
    #nev_rlg_recreate_thread.join()
    #nev_rltp_recreate_thread2.join()
    #nev_rlg_recreate_thread2.join()
    #nev_rlg_recreate_thread3.join()
    #nev_rltp_bump_thread.join()
    #nev_rlg_bump_thread.join()
    #choon_rlg_recreate_thread.join()
    #choon_rltp_bump_thread.join()
    #choon_rlg_bump_thread.join()
    #sam_rltp_bump_thread.join()
    #sam_rltp_recreate_thread.join()
    #sam_rltp_recreate_thread2.join()


def sigint_handler(signal, frame):
    print("[SIGINT] Exiting...")
    shutdown.set()

if __name__ == "__main__":
    shutdown = None
    total_rltp_trades = 0
    ws_server = None
    browser_connected = False
    browser_ws = None
    from my_items import my_items
    signal.signal(signal.SIGINT, sigint_handler)
    main()