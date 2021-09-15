import requests
import sys
import csv
import re
from unidecode import unidecode

url = 'http://localhost:5000/session/' + sys.argv[1] + '/add_training_data'

start = int(sys.argv[2])
stop = int(sys.argv[3])


good_name = 'places/places_trim.tsv'
bad_name = 'places/hotelscombined_trim.tsv'
matches_name = 'places/matches.tsv'


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

def readData(filename, idcol):
    """
    Read in our data from a CSV file and create a dictionary of records,
    where the key is a unique record ID.
    """

    data_d = {}

    with open(filename) as f:
        reader = csv.DictReader(f, delimiter="\t")
        for i, row in enumerate(reader):
            try:
                clean_row = dict([(k, preProcess(v)) for (k, v) in row.items()])
                if clean_row['latitude'] and clean_row['longitude'] and clean_row['latitude'] != "0" and clean_row['longitude'] != "0":
                    clean_row['location'] = (float(clean_row['latitude']), float(clean_row['longitude']))
                else :
                    # Add Empty Tuple
                    clean_row['Location'] = None
                data_d[clean_row[idcol]] = dict(clean_row)
                if i % 10000 == 0 and i > 0:
                    print('Processed {} Records'.format(i))
            except Exception as inst:
                print('Invalid Row: {0}'.format(i))
                print(inst)
    return data_d


# good = readData(good_name, 'destinyid')
# bad = readData(bad_name, 'id')

# with open(matches_name) as f:
#     csv_reader = csv.reader(f, delimiter="\t")
#     matches = list(csv_reader)


pairs = []
# for i in range(int(start), int(stop)):
#     gid = preProcess(str(matches[i][1]))
#     bid = preProcess(str(matches[i][0]))
#     #print("{} matches with {}".format(good[gid], bad[bid]))
#     # dedupe is super-picky about this - the non-canonical matches have to go first
#     pair = (bad[bid], good[gid])
#     pairs.append(pair)
pair = (
    {'id': '1', 'name':'Boston', 'country':'us', 'latitude':42.360903491390246, 'longitude':-71.05889023544313, 'type':'city'},{'id': '1', 'name':'Boston', 'country':'us', 'latitude':42.360903491390246, 'longitude':-71.05889023544313, 'type':'city'}
)
pairs.append(pair)
payload = {'match': pairs, 'distinct': []}

print("Searching in {} starting at {} and ending at {}".format(url, start, stop))

res = requests.post(url, json=payload)
if res.ok:
    print(res.json())




