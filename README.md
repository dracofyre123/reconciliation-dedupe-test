# W3C Reconciliation Service API with DeDeupe

This repo contains an example server that implements the [W3C Reconciliation Service API](https://reconciliation-api.github.io/specs/latest/) by using the [DeDupe Python Library](https://docs.dedupe.io/en/latest/).

It is based on an [example server](https://github.com/mblwhoi/reconciliation_service_skeleton) from the Woods Hole Oceanographic Institution and the [DeDupe Gazetteer Example](https://github.com/dedupeio/dedupe-examples/tree/master/gazetteer_example). 

The DeDupe example code is licensed MIT License Copyright (c) 2016 DataMade LLC. The Woods Hole code did not come with a license but as its README file states "This repository is intended to be a basic template for a Google Refine reconciliation service.  It is expected that you would modify the included code for your own purposes." I am assuming that it is under a permissive license. The new code that I have added is available under the MIT license to match the DeDuple license, but it's pretty hacky and is only intended for demo purposes.

**To reiterate: this code is super-hacky - it's hard-coded against one dataset and in many places doesn't check return values or validate the inputs its gets from the network. You really shouldn't run this.**

The dataset is the 'restaurants' dataset from [Professor AnHai Doan's Magellan Data Repository](https://sites.google.com/site/anhaidgroup/useful-stuff/data). It's a pretty small dataset but is simple to get started with. (Specifically, this is from the 'The Corleone Data Sets for EM' collection)

## Protocol Extension
The purpose of this server was to explore extending the Reconciliation Protocol to add a notion of a 'session' to the workflow, and to use that session to add additional example matches as training data. I picked the DeDupe library because it supported a 'Gazetteer'-style interface for entity matching, e.g. match a set of candidates entities to a canonical set of entities, and DeDupe had nice support for iterative training and retraining. The 'session' and 'add_training_data' endpoints are not standard in the Reconciliation API, nor is the 'session' key in the data that is posted to the '/reconcile' API endpoint. See [this issue on Github](https://github.com/reconciliation-api/specs/issues/30)

## Getting Started

First, initialize a database. This will also create a directory to store the DeDeupe learned settings files and training examples. The session data is stored in an SQLite database so this command creates or resets the table.

```
python initdb.py
```

Next, start the reconciliation server
```
python recon.py
```

In a different window, first create a new session
```
curl -X POST http://localhost:5000/session
```
That will create a new session to use - copy the returned GUID to a file or a notepad somewhere - that's the session ID and we'll reuse that from here on out. Next, upload some training data:

```
python upload_matches.py bdae4e03-b232-47db-96d7-0a36e6a2164d 5 20
```

That uses the file in ```restaurants/matches_fodors_zagats.csv``` to pick examples from the Fodors data (which is our 'canonical' dataset) with known matches from the Zagat data. In particular, the example command above uploads 15 matches - using rows 5 through 20 of the 'matches' file. The matches file has two columns - the first is the row ID from the Fodors dataset, and the second column is the row ID from the Zagat data of a match. ```upload_matches``` pulls out those records and sends them to the reconciliation API server, which uses the DeDeupe ```mark_pairs``` API to treat them as positive matches, and then the recon.py server retrains its matcher using those new examples. After retraining, the recon.py server writes out the new settings/weights file that's tied to this session and updates the session database to point to the new settings file for this session.

You can add additional training examples - for instance, you can add another 15 training examples:

```
python upload_matches.py bdae4e03-b232-47db-96d7-0a36e6a2164d 21 35
```

The reconciliation server will add those 15 new matching example pairs (rows 21-35 from the file of matches) to the previously uploaded example matching pairs and will retrain its weights for this session using all 30 example matching pairs.

Next, you can query the service to look for matching restaurants. 
```
python test_search.py bdae4e03-b232-47db-96d7-0a36e6a2164d caffe
```

This version of the reconciliation service looks for the session entry in the POST request, but if it's not there it falls back to a basic pretrained settings file that I checked into github. You can retrain it using the included ```gazetteer_example.py``` file, which is almost verbatim taken from the dedupe-examples repo, just changed to use the restaurants dataset. Because the session parameter is still optional, this server does work with the [Reconciliation Testbench web app](https://reconciliation-api.github.io/testbench/) - just set the server to be ```http://localhost:5000/reconcile``` and you can get a basic GUI for the service.

## Todo
The server is hard-coded to use the restaurants dataset. It would be nice to make that more flexible.

This server is not safe for concurrent HTTP requests. DeDupe by default will try to use multiple processors for training on Linux, which will likely not play nicely with Flask. (I've only tested on a Mac where I don't think it does that) The ```add_training_data``` endpoint also blocks until retraining is done, which could be a few seconds or even longer. The protocol extensions I've added should be smarter to handle this 'training' state or at least figure out what should happen if a request for a match comes in while there's still a training process happening in the background, or if two retraining requests come in at the same time. A real server implementation would also pass the retraining request off to a background job manager rather than blocking the HTTP server and training in the HTTP server process. 

The reconciliation API is designed around searching for a primary ID string, e.g. you normally use it to match something like city names to IDs from a database of cities - the use case was to use a tool like OpenRefine to match datasets to knowledge graphs like Wikidata, so the resulting 'reconciled record' is matched to an ID in the knowledge graph. And at the moment, the ```recon.py``` only considers the 'name' column of the Fodors and Zagat datasets for matching. However, the reconciliation protocol can include additional properties/columns in the request, and the DeDeue Gazetteer API can match records using multiple columns, so adding in support multiple columns would be a good addition. The limitation is the Testbench application can't send them, and DeDupe seems to be pretty sensitive to what columns it is trained on, even if columns are marked as potentially being missing. So, for this first version I limited the search to only the 'name' column. 

The Gazetteer DeDupe use case is really built around having a file of all the "messy" data that you're trying to match against the canonical dataset, which isn't quite the usecase we have in the reconciliation API - we don't have the full "messy" dataset. However, in order to train, the ```Gazetteer``` python object needs both datasets. (The pretrained ```StaticGazetteer``` object does not have this requirement) Because this server is hardcoded to use restaurants, we can give the ```Gazetteer``` object both the messy and canonical dataset, but it'd be better to convert the uploaded training data into a small "messy" dataset. 

DeDupe supports including example 'non-matching' pairs, and in fact it is pretty critical to DeDupe's training process to have examples that explicitly do not match to help it fine-tune the thresholds and weights. 

DeDupe's normal workflow is train on a handful of examples but also be provided with a number of unlabeled pairs. DeDeupe then uses that first training to try to label/match the unlabeled pairs, and then selects a subset of those newly-matched pairs and asks the user to tell DeDupe if it got the match right or wrong (this is a  'human-in-the-loop' workflow). DeDupe uses this feedback on the sample matches to retrain and repeat the cycle of asking the users how well it did with the matches, ideally getting more and more accurate after each cycle. DeDupe purposefully selects the examples that it is "least sure" about when asking for feedback. You can see it in action by running the ```gazetteer_example.py``` tool, which does a console-based human in the loop workflow.

It would not be hard to add negative match examples to the upload_matches tool and corresponding ```add_training_data``` endpoint, though the workflow of selecting candidate matches to iteratively ask the user for feedback on does not fit nicely with the OpenRefine tool. The [DeDupe.io](DeDupe.io) service, which is a hosted version of the DeDupe Python library, has really nailed the user experience for this sort of workflow.

```upload_matches``` was set up to make it easy to split the matches file into a training and test set, so a simple utility that read the unused matches from the matches file and checked for accuracy would a useful little tool.