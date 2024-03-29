# --- CONSTANTES ---

# Segundos a esperar el CONNECT de la otra parte
# de la conexión cuando se crea el socket con listener
CONNECT_WAIT_TIMEOUT = 10

# Segundos a esperar el CONNACK luego de enviar un CONNECT
# antes de reintentar enviar el CONNECT
CONNACK_WAIT_TIMEOUT = 1.5

# Segundos que espera el thread que envio el FINACK
# antes de cerrarse (durante esta espera verifica que
# no llegue otro FIN, lo que significa que no llegó el
# FINACK)
FIN_WAIT_TIMEOUT = 7

# Segundos a esperar el FINACK luego de enviar un FIN
# antes de reintentar enviar el FIN
FINACK_WAIT_TIMEOUT = 1.5

# Cantidad de reintentos a reenviar FIN o FINACK
FIN_RETRIES = 10

# Segundos a esperar el primer INFO que confirma el CONNACK
INITIAL_INFO_TIMEOUT = 5

# Cantidad de veces a reintentar enviar el CONNECT y CONNACK
# antes de fallar
CONNECT_RETRIES = 50

# Cada cuandos segundos reenviar un paquete que para el cual
# no se recibió el ACK
ACK_TIMEOUT = 1.5

# Cantidad de veces a reintentar enviar un paquete
# antes de cerrar la conexion
ACK_RETRIES = 50

# Primer numero de secuencia a enviar. Entre 0 y ACK_NUMBERS-1
INITIAL_PACKET_NUMBER = 0

# ~MTU. Maximum UDP payload is 65527, minus mux-demux header (6 bytes),
# minus our header (7 bytes) so this can't be geater than 65514
MAX_SIZE = 62000

# Cada cuando interrumpir el bloqueo para checkear si se esta
# cerrando el socket
STOP_CHECK_INTERVAL = 0.1

# Cada cuanto checkear en el recv (si no tiene timeout) y
# en el send si se cerro la conexion
CLOSED_CHECK_INTERVAL = 1

# Constantes del header de los paquetes
PACKET_NUMBER_BYTES = 4
PACKET_SIZE_BYTES = 2

# Siempre se debe cumplir WINDOW_SIZE < ACK_NUMBERS / 2
WINDOW_SIZE = 500
ACK_NUMBERS = 1 << 8 * PACKET_NUMBER_BYTES
# 4294967296 si PACKET_NUMBER_BYTES = 4

# --- CONSTANTES DE ESTADOS ---

# No envie el CONNECT (si soy socket) ni lo recibi (si soy listener)
NOT_CONNECTED = "NOT_CONNECTED"
# Soy Socket de listener, y recibi el CONNECT
CONNECTED = "CONNECTED"
# Se ejecutó .close()
CLOSED = "CLOSED"
# No me estan respondiendo, quiero cerrar sin coordinar
FORCED_CLOSING = "FORCED_CLOSING"
# No ejecuté .close() pero el otro me mando un FIN
PEER_CLOSED = "PEER_CLOSED"
