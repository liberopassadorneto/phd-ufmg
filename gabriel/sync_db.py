import os
import glob
import boto3
from boto3.s3.transfer import TransferConfig
import configparser

def load_sync_config(conf_path="config.conf"):
    config = configparser.ConfigParser()
    config.read(conf_path, encoding='utf-8')
    
    return {
        "s3_endpoint": config.get("S3", "endpoint"),
        "s3_key": config.get("S3", "access_key"),
        "s3_secret": config.get("S3", "secret_key"),
        "bucket_name": config.get("S3", "bucket_name"),
        "output_dir": config.get("DEFAULT", "output_dir", fallback="output")
    }

class S3Uploader:
    def __init__(self, s3_endpoint, s3_key, s3_secret, bucket_name):
        self.bucket_name = bucket_name
        self.s3 = boto3.client(
            's3',
            endpoint_url=s3_endpoint,
            aws_access_key_id=s3_key,
            aws_secret_access_key=s3_secret
        )

    def check_connection(self):
        """Testa se o bucket existe e cria-o caso não exista."""
        print(f"Testando ligação com o endpoint {self.s3.meta.endpoint_url}...")
        try:
            self.s3.head_bucket(Bucket=self.bucket_name)
            print(f"✓ Ligação bem-sucedida! O bucket '{self.bucket_name}' já existe e está acessível.")
            return True
        except Exception as e:
            error_msg = str(e)
            if '404' in error_msg or 'Not Found' in error_msg or 'NoSuchBucket' in error_msg:
                print(f"O bucket '{self.bucket_name}' não foi encontrado. A iniciar a criação...")
                try:
                    self.s3.create_bucket(Bucket=self.bucket_name)
                    print(f"✓ Bucket '{self.bucket_name}' criado com sucesso!")
                    return True
                except Exception as create_error:
                    print(f"❌ Falha ao criar o bucket: {create_error}")
                    return False
            else:
                print(f"❌ Falha de ligação ou permissão negada: {e}")
                return False

    def get_existing_keys(self):
        """Mapeia todos os arquivos que já existem no bucket S3 usando paginação."""
        print("Mapeando arquivos já existentes no bucket... (isso pode levar alguns segundos)")
        existing_keys = set()
        paginator = self.s3.get_paginator('list_objects_v2')
        
        try:
            for page in paginator.paginate(Bucket=self.bucket_name):
                if 'Contents' in page:
                    for obj in page['Contents']:
                        existing_keys.add(obj['Key'])
            print(f"✓ Mapeamento concluído: {len(existing_keys)} arquivos já estão no S3 e serão ignorados.")
        except Exception as e:
            print(f"Aviso: Não foi possível listar o bucket ({e}). O script tentará enviar tudo.")
            
        return existing_keys

    def upload_asset(self, local_path, s3_rel_path):
        GB = 1024 ** 3
        config = TransferConfig(multipart_threshold=5 * GB)
        
        self.s3.upload_file(
            local_path, 
            self.bucket_name, 
            s3_rel_path,
            Config=config
        )

def sync_all_folders(uploader, output_dir):
    if not os.path.exists(output_dir):
        print(f"[Erro] Diretório de saída não encontrado: {output_dir}")
        return

    existing_keys = uploader.get_existing_keys()

    video_folders = [f for f in os.listdir(output_dir) if os.path.isdir(os.path.join(output_dir, f))]
    print(f"Encontradas {len(video_folders)} pastas no diretório '{output_dir}'.")

    for video_id in video_folders:
        video_folder = os.path.join(output_dir, video_id)
        
        arquivos_para_enviar = []
        for local_path in glob.glob(f"{video_folder}/**/*", recursive=True):
            if os.path.isfile(local_path):
                arquivos_para_enviar.append(local_path)
                
        if not arquivos_para_enviar:
            continue
            
        enviados_agora = 0
        ignorados = 0
        
        for local_path in arquivos_para_enviar:
            rel_path_to_video = os.path.relpath(local_path, video_folder)
            s3_rel_path = f"data/{video_id}/{rel_path_to_video}".replace("\\", "/")
            
            if s3_rel_path in existing_keys:
                ignorados += 1
                continue
            
            uploader.upload_asset(local_path, s3_rel_path)
            enviados_agora += 1
            
        if enviados_agora > 0:
            print(f"✓ {video_id}: {enviados_agora} arquivos enviados (ignorados: {ignorados})")
        else:
            print(f"⏭️ {video_id}: Já 100% sincronizado (ignorados: {ignorados})")

if __name__ == "__main__":
    cfg = load_sync_config("config.conf")
    
    uploader = S3Uploader(
        s3_endpoint=cfg["s3_endpoint"],
        s3_key=cfg["s3_key"],
        s3_secret=cfg["s3_secret"],
        bucket_name=cfg["bucket_name"]
    )
    
    if uploader.check_connection():
        sync_all_folders(uploader, cfg["output_dir"])
    else:
        print("Execução abortada. Verifique as configurações.")