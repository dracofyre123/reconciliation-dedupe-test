from unidecode import unidecode
import re


def preProcessColumnValue(column:str):
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

def processPlace(place: dict):
    clean_row = dict()
    clean_row['name'] = preProcessColumnValue(place.get('name'))
    clean_row['country'] = preProcessColumnValue(place.get('country'))
    clean_row['type'] = preProcessColumnValue(place.get('type'))
    clean_row['latitude'] = place.get('latitude', None)
    clean_row['longitude'] = place.get('longitude', None)

    if clean_row['latitude'] and clean_row['longitude'] and clean_row['latitude'] !=  0 and clean_row['longitude'] != 0:
        clean_row['location'] = (float(clean_row['latitude']), float(clean_row['longitude']))
    else :
        # Add Empty Tuple
        clean_row['location'] = None
    for (k,v) in place.items():
        if k not in clean_row:
            if isinstance(v, str) :
                clean_row[k] = preProcessColumnValue(v)
            else:
                clean_row[k] = v
    return clean_row