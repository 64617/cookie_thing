#!/bin/bash
CONTAINER=caption-db
SRCPATH=/captions-latest.pgdump
TIME=$(date '+%s-%b-%d-%H')                # This Command will read the date.
FILENAME=captions-$TIME.pgdump             # The filename including the date.
DESDIR="$HOME"/output_backups              # Destination of backup file.
echo "RUNNING AT $TIME" >> $DESDIR/cronlog.log
docker exec "$CONTAINER" pg_dump -F c -f "$SRCPATH" derpibooru || exit
docker cp "$CONTAINER:$SRCPATH" "$DESDIR/$FILENAME" || exit
SYMLINK="$DESDIR/captions-latest.pgdump"
unlink $SYMLINK
ln -s "$FILENAME" $SYMLINK
