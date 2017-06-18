"""
BBC Election 2017 Declaration Parser
(C) Luke Hutton 2017
"""

import json
from lxml import html
import phue
import random
import requests
from rgbxy import Converter
import threading
import time

import tornado.escape
import tornado.ioloop
import tornado.options
import tornado.web
import tornado.websocket

SEAT_ROOT = "http://www.bbc.co.uk/news/politics/constituencies/"
USER_AGENT_HEADER = {'User-Agent':"ElectionHue/1.0"}

random = random.SystemRandom()

declares = {}
unannounced = []
seats = {}

BRIDGE_IP = '192.168.1.39'
b = None

def get_constituency_ids():
    """
    Parse out the unique ID for each seat and save to json. Only need to run once!
    """
    seats_index_url = "http://www.bbc.co.uk/news/politics/constituencies"
    page = requests.get(url=seats_index_url, headers=USER_AGENT_HEADER)
    tree = html.fromstring(page.text)

    xpath = "//th/a"
    seats = tree.xpath(xpath)


    seat_dict = {}
    for seat in seats:
        c_id = seat.xpath("@href")[0].split("/news/politics/constituencies/")[1]
        name = seat.xpath("text()")[0]

        seat_dict[c_id] = name


    with open('seat_ids.json', 'w') as outfile:
        json.dump(seat_dict, outfile)

result_xpath = "//span[contains(@class, 'results-flash__new-party')]"
result_old_xpath = "//span[contains(@class, 'results-flash__old-party')]"
mp_name_xpath = "//span[contains(@class, 'results-table__body-text')]/text()"
votes_xpath = "//li[contains(@class, 'party__result--votesshare')]/text()"
change_xpath = "//li[contains(@class, 'party__result--votesnet')]/span[1]/text()"

colors = {'lab': "ed1e0e", 'con': "0575c9", 'lib': "feae14", 'snp':'ebc31c',
        'dup':'c0153d', 'pc':'4e9f2f', 'ind':'d26fbc'}

def get_result_for_lights(seat):
        converter = Converter()

        xy_old = converter.hex_to_xy(colors[seat['old_party']])
        xy_new = converter.hex_to_xy(colors[seat['new_party']])

        comm = {'bri':127, 'transitiontime':20, 'xy':xy_old}
        b.set_light(LIGHTS, comm)

        time.sleep(5)
        comm = {'bri':254, 'transitiontime':20, 'xy':xy_new}
        b.set_light(LIGHTS, comm)

        time.sleep(20)

        state_of_the_parties()
        #comm = {'bri':254, 'transitiontime':20, 'sat':0}
        #b.set_light(LIGHTS,comm)


def get_result_by_seat_tree(seat_id,tree):
    """
        Provide the tree for a seat's page and get a nice
        dict with all the result data in an easy to consume way
    """

    result = tree.xpath(result_xpath)[0]
    result_text = result.text_content()
    new_party = result.get('class').split(" ")[2].split("--")[1]

    result = tree.xpath(result_old_xpath)[0]
    result_text = result.text_content()
    old_party = result.get('class').split(" ")[2].split("--")[1]

    winner = tree.xpath(mp_name_xpath)[0]
    votes = tree.xpath(votes_xpath)[0]
    change = tree.xpath(change_xpath)[0]

    result_out = {'seat_name':seats[seat_id], "seat_id":seat_id, "old_party":old_party,
    "new_party":new_party, "mp_name":winner, 'votes':votes, 'change':change}

    print result_out

    return result_out


def light_pump():
    global active_effect

    while(True):
        if(len(unannounced) > 0 and active_effect == False):
            pick = random.choice(unannounced)
            get_result_for_lights(pick)
            unannounced.remove(pick)

        time.sleep(1)


party_order_xpath = "//abbr[contains(@class,'ge2017-banner__abbr')]/text()"
party_seats_xpath = "//tr[contains(@class,'ge2017-banner__row--seats')]/td/span/text()"
home_url = "http://www.bbc.co.uk/news/election/2017"

def state_of_the_parties():
    global b

    while(True):
        page = requests.get(url=home_url,headers=USER_AGENT_HEADER)
        tree = html.fromstring(page.text)

        parties = []
        parties_tree = tree.xpath(party_order_xpath)
        #for party in parties_tree:
        print parties_tree
        party_seats = tree.xpath(party_seats_xpath)
        print party_seats

        results = {}
        con_idx = parties_tree.index('CON')
        results['CON'] = float(party_seats[con_idx])

        lab_idx = parties_tree.index('LAB')
        results['LAB'] = float(party_seats[lab_idx])

        snp_idx = parties_tree.index('SNP')
        results['SNP'] = float(party_seats[snp_idx])

        total_seats = float(results['CON'] + results['LAB'] + results['SNP'])
        brightness = {}
        brightness['CON'] = results['CON']/total_seats
        brightness['LAB'] = results['LAB']/total_seats
        brightness['SNP'] = results['SNP']/total_seats

        converter = Converter()


        light_count = 0
        for party in results:
            bri = int(brightness[party]*254)
            xy = converter.hex_to_xy(colors[party.lower()])

            comm = {'bri':bri, 'transitiontime':20, 'xy':xy}
            b.set_light(LIGHTS[light_count], comm)
            light_count += 1

        time.sleep(10)



def detect_declaration_pump():
    global seats, unannounced
    with open('seat_ids.json','r') as infile:
        seats = json.load(infile)




    while(True):
        test_seat = random.choice(seats.keys())
        print "Testing declaration status of %s" % seats[test_seat]

        if(test_seat) in declares:
            print "Constituency already declared. Trying another..."
            time.sleep(1)
            continue

        #test_seat = "E14000831"
        page = requests.get(url=SEAT_ROOT+test_seat,headers=USER_AGENT_HEADER)
        tree = html.fromstring(page.text)


        try:
            result = get_result_by_seat_tree(test_seat,tree)
            unannounced.append(result)
            declares[test_seat] = tree
            print "Declaration complete"
        except:
            print "Not yet declared"
            #raise


        time.sleep(3)

class Application(tornado.web.Application):
	def __init__(self):
		handlers = [
			(r"/socket", NewDeclareHandler),
            (r"/stop", StopHandler)
			]
		tornado.web.Application.__init__(self, handlers, debug=True)

class StopHandler(tornado.web.RequestHandler):
    def get(self):
        tornado.ioloop.IOLoop.instance().stop()

class NewDeclareHandler(tornado.web.RequestHandler):
    """
        Returns data about the latest seat to be declared which hasn't
        yet been consumed.
        Since seats may be declared faster than they can be presented to
        the client, they are only considered consumed when returned by this
        endpoint
    """
    def get(self):
        global seats, unannounced
        return

        if(len(unannounced) > 0):
            item = random.choice(unannounced)
            unannounced.remove(item)
            self.write(json.dumps(item))

        else:
            obj = {'status':'no_declares'}
            self.write(json.dumps(obj))

LIGHTS = [4,6,7] # living room
light_set = []
active_effect = False

if __name__ == "__main__":
    global b, light_set, active_effect




    b = phue.Bridge(BRIDGE_IP)
    b.get_api()
    lights = b.get_light_objects('id')
    light_set = []
    for light_id, light in lights.iteritems():
        if light_id not in LIGHTS:
            continue
        light_set.append(light)

    state_of_the_parties()

    app = Application()
    app.listen(7000)

    t = threading.Thread(target=tornado.ioloop.IOLoop.instance().start)
    t.start()

    l = threading.Thread(target=light_pump)
    l.start()

    detect_declaration_pump()
