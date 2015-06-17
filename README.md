# soplex

```
pip install git+https://github.com/tcr3dr/soplex.git
```

## demo

````
soplex tcp:server:5000 tcp:server:5555
soplex tcp:client:5000 tcp:client:5999
nc localhost 5555
nc -l 5999 # and type
````

## license

MIT/ASL2
