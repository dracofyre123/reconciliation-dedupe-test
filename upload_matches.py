import requests
import sys
import csv
import re
from unidecode import unidecode

url = 'http://localhost:5000/session/' + sys.argv[1] + '/add_training_data'

start = int(sys.argv[2])
stop = int(sys.argv[3])


good_name = 'restaurants/fodors.csv'
bad_name = 'restaurants/zagats.csv'
matches_name = 'restaurants/matches_fodors_zagats.csv'


def preProcess(column):
    """
    Do a little bit of data cleaning with the help of Unidecode and Regex.
    Things like casing, extra spaces, quotes and new lines can be ignored.
    """

    column = unidecode(column)
    column = re.sub('\n', ' ', column)
    column = re.sub('-', '', column)
    column = re.sub('/', ' ', column)
    column = re.sub("'", '', column)
    column = re.sub(",", '', column)
    column = re.sub(":", ' ', column)
    column = re.sub(' +', ' ', column)
    column = column.strip().strip('"').strip("'").lower().strip()
    if not column:
        column = None
    return column

def readData(filename):
    """
    Read in our data from a CSV file and create a dictionary of records,
    where the key is a unique record ID.
    """

    data_d = {}

    with open(filename) as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            clean_row = dict([(k, preProcess(v)) for (k, v) in row.items()])
            data_d[clean_row['id']] = dict(clean_row)

    return data_d


good = readData(good_name)
bad = readData(bad_name)

with open(matches_name) as f:
    csv_reader = csv.reader(f)
    matches = list(csv_reader)


pairs = []
for i in range(int(start), int(stop)):
    gid = str(matches[i][0])
    bid = str(matches[i][1])
    #print("{} matches with {}".format(good[gid], bad[bid]))
    # dedupe is super-picky about this - the non-canonical matches have to go first
    pair = (bad[bid], good[gid])
    pairs.append(pair)
payload = {'match': pairs, 'distinct': []}

print("Searching in {} starting at {} and ending at {}".format(url, start, stop))

res = requests.post(url, json=payload)
if res.ok:
    print(res.json())




