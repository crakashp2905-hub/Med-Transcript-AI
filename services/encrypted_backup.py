"""Authenticated streaming backup envelopes; infrastructure key custody remains external."""
import argparse
import os
from pathlib import Path
import tempfile
from uuid import uuid4
import zipfile

from services.api.ingest import file_sha256
from services.maintenance import backup,restore,checked

MAGIC=b'MTAI-CBL1\0'
CONTEXT=b'med-transcript synthetic backup envelope v1'
DEFAULT_BUDGET=2*1024**3


def crypt_file(source,destination,key,*,decrypt=False,max_bytes=DEFAULT_BUDGET):
    from cryptography.cobblestone import Cobblestone128Encryptor,Cobblestone128Decryptor
    if len(key)!=16 or not 1<=max_bytes<=1024**4:raise ValueError('Invalid key or size budget')
    source,destination=Path(source),Path(destination)
    if destination.exists():raise FileExistsError('Refusing to replace existing output')
    temporary=destination.with_name(destination.name+'.'+str(uuid4())+'.part')
    cipher=(Cobblestone128Decryptor if decrypt else Cobblestone128Encryptor)(key,context=CONTEXT)
    processed=0
    try:
        with source.open('rb') as incoming,temporary.open('xb') as output:
            os.chmod(temporary,0o600)
            if decrypt:
                if incoming.read(len(MAGIC))!=MAGIC:raise ValueError('Unsupported encrypted envelope')
            else:output.write(MAGIC)
            while data:=incoming.read(1024*1024):
                processed+=len(data)
                if processed>max_bytes:raise ValueError('Backup size budget exceeded')
                output.write(cipher.update(data))
            output.write(cipher.finalize());output.flush();os.fsync(output.fileno())
        # Publish only after full authentication, and never overwrite a racing output.
        os.link(temporary,destination)
    finally:temporary.unlink(missing_ok=True)
    return {'encrypted':not decrypt,'bytes':destination.stat().st_size,'sha256':file_sha256(destination)}


def encrypted_backup(db,assets,destination,key,*,max_bytes=DEFAULT_BUDGET):
    destination=Path(destination).resolve()
    if destination.exists():raise FileExistsError('Refusing to replace existing backup')
    destination.parent.mkdir(parents=True,exist_ok=True)
    # Temporary plaintext requires a protected/encrypted staging volume in deployment.
    with tempfile.TemporaryDirectory(prefix='mt-backup-',dir=destination.parent) as temporary:
        root=Path(temporary).resolve();os.chmod(root,0o700)
        source=root/'source';receipt=backup(db,assets,source)
        archive=root/'snapshot.zip'
        total=0
        with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_STORED) as output:
            for path in sorted(source.rglob('*')):
                if path.is_file():
                    total+=path.stat().st_size
                    if total>max_bytes:raise ValueError('Backup size budget exceeded')
                    output.write(path,path.relative_to(source).as_posix())
        envelope=crypt_file(archive,destination,key,max_bytes=max_bytes+1024**2)
    return {'status':'encrypted_backup_created','algorithm':'Cobblestone-128','files':receipt['files'],
            'ciphertext_sha256':envelope['sha256'],'encrypted':True,'managed_key_custody_verified':False}


def encrypted_restore(source,destination,tombstones_from,key,*,max_bytes=DEFAULT_BUDGET):
    destination=Path(destination).resolve()
    if destination.exists():raise FileExistsError('Restore destination must be new')
    destination.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='mt-restore-',dir=destination.parent) as temporary:
        root=Path(temporary).resolve();os.chmod(root,0o700)
        archive=root/'authenticated.zip'
        crypt_file(source,archive,key,decrypt=True,max_bytes=max_bytes+1024**2)
        unpacked=root/'snapshot';unpacked.mkdir()
        with zipfile.ZipFile(archive) as package:
            entries=package.infolist();names=[e.filename.casefold() for e in entries]
            if len(entries)>100000 or len(set(names))!=len(names) or sum(e.file_size for e in entries)>max_bytes:
                raise ValueError('Archive extraction budget or uniqueness violation')
            for entry in entries:
                if entry.is_dir():continue
                if '\\' in entry.filename or ':' in entry.filename or entry.filename.startswith('/'):
                    raise ValueError('Unsafe archive path')
                target=checked(unpacked,entry.filename);target.parent.mkdir(parents=True,exist_ok=True)
                with package.open(entry) as incoming,target.open('xb') as output:
                    while chunk:=incoming.read(1024*1024):output.write(chunk)
        receipt=restore(unpacked,destination,tombstones_from)
    return {**receipt,'envelope_authenticated':True,'real_patient_release_authorized':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['keygen','backup','restore'])
    parser.add_argument('--key-file',required=True)
    parser.add_argument('--db');parser.add_argument('--assets');parser.add_argument('--source');parser.add_argument('--destination')
    parser.add_argument('--tombstones-from');parser.add_argument('--max-bytes',type=int,default=DEFAULT_BUDGET)
    args=parser.parse_args();keypath=Path(args.key_file)
    if args.action=='keygen':
        from cryptography.cobblestone import Cobblestone128Encryptor
        with keypath.open('xb') as target:target.write(Cobblestone128Encryptor.generate_key())
        os.chmod(keypath,0o600)
        result={'status':'key_created','secret_printed':False,'custody_requires_operator':True}
    else:
        key=keypath.read_bytes()
        if args.action=='backup':
            if not args.db or not args.assets or not args.destination:parser.error('backup requires db, assets and destination')
            result=encrypted_backup(args.db,args.assets,args.destination,key,max_bytes=args.max_bytes)
        else:
            if not args.source or not args.destination or not args.tombstones_from:parser.error('restore requires source, destination and tombstones-from')
            result=encrypted_restore(args.source,args.destination,args.tombstones_from,key,max_bytes=args.max_bytes)
    import json
    print(json.dumps(result))


if __name__=='__main__':main()
