# bottle

A bot that plays wordles.


```
$ bottle play 0
Loading Wordle #0
Loading words from nytimes
Wordle #0 4/6*

ＹＥＡＲＳ
⬜⬜🟨🟨⬜
ＬＡＲＮＴ
⬜🟨🟨⬜⬜
ＯＲＧＩＡ
⬜🟨🟩🟨🟨
ＣＩＧＡＲ
🟩🟩🟩🟩🟩
😑
```

## Sharing output

If you want to share the output, just add `--share` to avoid sharing spoilers:

```
$ bottle play --strategy=weighted --share
Loading Wordle #283
Loading words from nytimes
Wordle #283 5/6*

🟨🟨⬜⬜🟨
🟩⬜🟩🟩⬜
🟩⬜🟩🟩⬜
🟩🟩🟩🟩⬜
🟩🟩🟩🟩🟩
😢
```

## Bulk testing

The `bulk` command runs all the wordles to date (or the first N wordles with `-n N`):

```
$ bottle bulk -n 100
Loading Wordle #1
Loading words from nytimes
...
Did 100 puzzles in 433 total guesses (4.3 avg) (successes=97 (97.00%)
```
