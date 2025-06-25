DISPLAY=${DISPLAY:-:0}
export DISPLAY

log() {
	#local timestamp
	timestamp=$(date +"%Y-%m-%d %H:%M:%S")
	echo "$timestamp  $1"
}
