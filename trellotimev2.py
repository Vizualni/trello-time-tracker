import trello
import datetime
import dateutil.parser
import pytz
import argparse
import urllib
import os
import threading
from Queue import Queue

from config import *

qin = Queue()
qout = Queue()
def parse_time(time):
    return dateutil.parser.parse(time).replace(tzinfo=pytz.utc)

def get_comments_string(comment_list):
    return '\n'.join(map(lambda x: '- {}'.format(x), reversed(comment_list)))

lists = {}

def getset_list(trello_api, list_id):
    if list_id in lists:
        return lists[list_id]['name']

    current_list = trello_api.lists.get(list_id)
    lists[list_id] = current_list
    return current_list['name']

def calculate_time_doing(card):
    time = datetime.timedelta()
    card_data = trello_api.cards.get_action(card['id'])
    start_time = datetime.datetime.fromtimestamp(int(card['id'][:8], 16)).replace(tzinfo=pytz.utc) - datetime.timedelta(hours=2)
    current_list = getset_list(trello_api, card['idList'])
    reversed_list = list(reversed(filter(lambda x: x['type'] == 'updateCard', card_data)))
    card['start_time'] = start_time

    for history in reversed_list:
        # usao u doing karticu
        if history['data']['listAfter']['name'] == CARD_NAME:
            start_time = parse_time(history['date'])
        # izasao iz doing kartice
        elif history['data']['listBefore']['name'] == CARD_NAME:
            time += parse_time(history['date']) - start_time
    # if card is still in doing
    if current_list == CARD_NAME:
        now = datetime.datetime.now().replace(tzinfo=pytz.utc) - datetime.timedelta(hours=2)  # tricky shit... :(
        time += now - start_time
    card['time'] = time
    return time

def get_logs(trello_api):
    board_cards = trello_api.boards.get_card(BOARD)
    time_delta = datetime.timedelta()
    threads = []
    for card in board_cards:
        # add to queue
        qin.put(card)

    for t in xrange(5):
        tt = threading.Thread(target=thread_get_comments, args=(trello_api,))
        tt.daemon = True
        tt.start()
        threads.append(tt)

    # be carefull with this shiiieeet
    # if you have 10000 cards in trello
    # you will have 10000 threads.
    for card in board_cards:
        tt2 = threading.Thread(target=calculate_time_doing, args=(card,))
        tt2.daemon = True
        tt2.start()
        threads.append(tt2)

    for t in threads:
        t.join()

    for card in board_cards:
        time_delta += card['time']

    return board_cards

def thread_get_comments(trello_api):
    while True:
        try:
            card = qin.get(timeout=1)
        except Exception, e:
            break
        card['comments'] = []
        for comment in filter(lambda x: x['type'] == 'commentCard', trello_api.cards.get_action(card['id'])):
            card['comments'].append(comment['data']['text'])
        qin.task_done()

def round_time(time):
    return "{h:02d}h{m:02d}".format(h=time.seconds/60/60, m=time.seconds/60%60)

def chop_microseconds(delta):
    return delta - datetime.timedelta(microseconds=delta.microseconds)

def doing_now(trello_api):
    total_time = datetime.timedelta()
    for card in trello_api.boards.get_card(BOARD):
        if getset_list(trello_api, card['idList']) == CARD_NAME:
            time = calculate_time_doing(card)
            os.system("""notify-send -i face-glasses -u normal "{}" "{}" """.format(card['name'], "Currently doing "+str(chop_microseconds(time))))
            break


def calculate_all(token_api):
    save = open(SAVE_LOGS_PATH + str(datetime.datetime.now()) + '.html', "w")
    save.write('<meta charset="UTF-8">')
    total_time = datetime.timedelta()

    for card_log in get_logs(trello_api):
        total_time += card_log['time']
        print round_time(card_log['time'])
        print card_log['name']
        print get_comments_string(card_log['comments'])
        save.write("""
            <div><h2>{}</h2><h3>{}</h3><pre>{}</pre></div>
            <div>
            <a href="http://logger.trikoder.net/work-log/add/?form_work_log_description_raw={}&form_work_log_date={}&form_work_log_time={}" target="_blank">Unesi u logger.trikoder.com</a>
            </div></br></br>
            """.format(
                round_time(card_log['time']),
                card_log['name'],
                unicode(get_comments_string(card_log['comments'])).encode('utf-8'),
                urllib.quote(str(card_log['name']) + str("\n") + str(get_comments_string(card_log['comments']))),
                str(card_log['start_time'].date()),
                round_time(card_log['time'])
            )
        )
        print ''
    total_time_string = "Sveukupno vrijeme: {}".format(str(round_time(total_time)))
    print total_time_string
    save.write(total_time_string)
    save.close()
    file_path = os.path.abspath(save.name)
    print "Spremljeno u {}".format(file_path)
    os.system("gnome-open \"{}\"".format(file_path))

if __name__ == '__main__':
    if not os.path.exists(SAVE_LOGS_PATH):
        os.makedirs(SAVE_LOGS_PATH)
    parser = argparse.ArgumentParser(description='Calculate time.')
    parser.add_argument('command', type=str, help='Command to run: main or now')
    args = parser.parse_args()
    command = args.command

    trello_api = trello.TrelloApi(KEY, token=TOKEN)
    if command == 'main':
        calculate_all(trello_api)
    elif command == 'now':
        doing_now(trello_api)