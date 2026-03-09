# Board game recommendations

Get board game recommendations, thanks to Board Game Geek.

Examples:
```
python recommend.py "Wingspan" "Terraforming Mars" "Agricola"
python recommend.py --help
```

## Setting up

- Download the
  [Kaggle dataset by jvanelteren](https://www.kaggle.com/datasets/jvanelteren/boardgamegeek-reviews/)
  and put it into the `data` directory.
- Run `python import_ratings.py data/name-of-dataset/csv`.
- Get a BGG token and put into `data/token.json` like this:
```
{
    "name": "Recommendation1",
    "value": "0495-my-token-here-etc-af56e"
}
```

[Powered by BGG](https://drive.google.com/file/d/1unpb690BONNJB5HXtJEHfO4Raz7I-5JO/view?usp=drive_link)
