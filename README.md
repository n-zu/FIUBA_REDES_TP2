# TP2: File Transfer Protocol

## Requisitos

`pip install -r requirements.txt`

## Run

Create `hello.txt` file

Start server:

```
python3 src/start_server.py -H 127.0.0.1 -p 8080 -s server
```

Upload file:

```
python3 src/upload.py -H 127.0.0.1 -p 8080 -s . -n hello.txt
```

Download file:

```
python3 src/download.py -H 127.0.0.1 -p 8080 -d client -n hello.txt
```

## Switch between protocols

On `src/download.py` line 119, `src/upload.py` line 112 and
`src/start_server.py` line 151, set method to `"stop_and_wait"` or
`"selective_repeat"`

## CLI : Command Line Interface

### Client

#### Upload

```
> python upload - file -h
> usage : file - upload [ - h ] [ - v | -q ] [ - H ADDR ] [ - p PORT ] [ -s FILEPATH ] [ - n FILENAME ]
> < command description >
> optional arguments :
> -h , -- help show this help message and exit
> -v , -- verbose increase output verbosity
> -q , -- quiet decrease output verbosity
> -H , -- host server IP address
> -p , -- port server port
> -s , -- src source file p
```

#### Download

```
> python download - file -h
> usage : download - file [ - h ] [ -v | -q ] [ - H ADDR ] [ - p PORT ] [ - d FILEPATH ] [ - n FILENAME ]
> < command description >
> optional arguments :
> -h , -- help show this help message and exit
> -v , -- verbose increase output verbosity
> -q , -- quiet decrease output verbosity
> -H , -- host server IP address
> -p , -- port server port
> -d , -- dst destination file path
> -n , -- name file name
```

### Server

```
> python start - server -h
> usage : start - server [ - h ] [ - v | -q ] [ - H ADDR ] [ - p PORT ] [- s DIRPATH ]
> < command description >
> optional arguments :
> -h , -- help show this help message and exit
> -v , -- verbose increase output verbosity
> -q , -- quiet decrease output verbosity
> -H , -- host service IP address
> -p , -- port service port
> -s , -- storage storage dir path
```
