# TP2: File Transfer Protocol

## Requisitos

`pip install -r requirements.txt`

## Tests

Para ejecutar los tests, ejecutar el comando `pytest`

> Nota: Para ejecutar `test_rdt_listener.py` y `test_saw.py`:
>
> ```
> cd src
> python3 -m tests.test_rdt_listener
> python3 -m tests.test_saw
> ```

###### Nota (Z)

> Me anda medio mal python, esto me dio resultado:

Run test file: In `src`
```
python3 -m tests.test_sr
```

Run test: In `src/tests`
```
python3 -m pytest test_sr.py

```

Run test: In `src/tests` ( Also SLOW TESTS )
```
python3 -m pytest test_sr.py --runslow

```

## Draft

| Module | Client Functionalities              | Server Functionalities                               | Notes                    |
| ------ | ----------------------------------- | ---------------------------------------------------- | ------------------------ |
| CLI    | `upload-file.py` `download-file.py` | `start-server.py`                                    |
| FTP    | `upload` `download`                 | `startServer` `sendFile` `saveFile`                  | tlv                      |
| RDTP   | `connect` `send` `receive` `close`  | `listen` `acceptConnection` `send` `receive` `close` | tlv, connection oriented |

### CLI : Command Line Interface

#### Notes

- Use [argparse](https://docs.python.org/3/library/argparse.html)

#### Client

```
> python upload - file -h
usage : file - upload [ - h ] [ - v | -q ] [ - H ADDR ] [ - p PORT ] [ -s FILEPATH ] [ - n FILENAME ]
< command description >
optional arguments :
-h , -- help show this help message and exit
-v , -- verbose increase output verbosity
-q , -- quiet decrease output verbosity
-H , -- host server IP address
-p , -- port server port
-s , -- src source file p
```

```
> python download - file -h
usage : download - file [ - h ] [ -v | -q ] [ - H ADDR ] [ - p PORT ] [ - d FILEPATH ] [ - n FILENAME ]
< command description >
optional arguments :
-h , -- help show this help message and exit
-v , -- verbose increase output verbosity
-q , -- quiet decrease output verbosity
-H , -- host server IP address
-p , -- port server port
-d , -- dst destination file path
-n , -- name file name
```

#### Server

```
> python start - server -h
usage : start - server [ - h ] [ - v | -q ] [ - H ADDR ] [ - p PORT ] [- s DIRPATH ]
< command description >
optional arguments :
-h , -- help show this help message and exit
-v , -- verbose increase output verbosity
-q , -- quiet decrease output verbosity
-H , -- host service IP address
-p , -- port service port
-s , -- storage storage dir path
```

### FTP : File Transfer Protocol

#### Client

#### Server

### RDTP : Reliable Data Transfer Protocol

#### Notes

- Stop & Wait
- Selective Repeat

> 2 different modules with the same interface ?

#### Client

#### Server
