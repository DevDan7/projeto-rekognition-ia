import json
import boto3
import os
import urllib.parse
from datetime import datetime

# 1. Inicializar los clientes de AWS (boto3)
rekognition = boto3.client('rekognition')
dynamodb = boto3.resource('dynamodb')
sns = boto3.client('sns')

# 2. Variables de entorno
TABLE_NAME = os.environ['TABLE_NAME']
SNS_TOPIC_ARN = os.environ['SNS_TOPIC_ARN']

def lambda_handler(event, context):
    # 3. Extraer el nombre del bucket y DECODIFICAR el nombre del archivo (key)
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'])
    
    try:
        # 4. Llamar a la IA: Amazon Rekognition
        print(f"INICIANDO: Analizando la imagen '{key}' en el bucket '{bucket}'")
        
        response = rekognition.detect_faces(
            Image={'S3Object': {'Bucket': bucket, 'Name': key}},
            Attributes=['ALL']
        )
        
        faces = response.get('FaceDetails',[])
        mensaje_sns = f"Se analizó la imagen '{key}'. Rostros detectados: {len(faces)}.\n\n"
        
        # 5. Preparar la conexión a DynamoDB
        table = dynamodb.Table(TABLE_NAME)
        
        # 6. Lógica: Si hay rostros, extraemos los datos y los guardamos
        if faces:
            emocion = faces[0]['Emotions'][0]['Type']
            edad_min = faces[0]['AgeRange']['Low']
            edad_max = faces[0]['AgeRange']['High']
            
            mensaje_sns += f"Emoción principal: {emocion}.\nEdad estimada: {edad_min}-{edad_max} años."
            
            print(f"ÉXITO REKOGNITION: Se detectaron {len(faces)} rostros. Guardando en DynamoDB...")
            
            # Guardar en DynamoDB (PutItem)
            table.put_item(
                Item={
                    'NombreArchivo': key,
                    'FechaAnalisis': str(datetime.now()),
                    'RostrosDetectados': len(faces),
                    'EmocionPrincipal': emocion,
                    'EdadEstimada': f"{edad_min}-{edad_max}"
                }
            )
        else:
            print("ÉXITO REKOGNITION: No se detectaron rostros. Guardando en DynamoDB...")
            mensaje_sns += "No se detectaron rostros en la imagen."
            table.put_item(
                Item={
                    'NombreArchivo': key,
                    'FechaAnalisis': str(datetime.now()),
                    'RostrosDetectados': 0
                }
            )
            
        # 7. Enviar Alerta por SNS
        print("Enviando alerta por correo (SNS)...")
        sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject="AWS IA - Análisis Facial Completado",
            Message=mensaje_sns
        )
        
        print("PROCESO COMPLETADO AL 100%")
        return {
            'statusCode': 200,
            'body': json.dumps('Análisis completado con éxito!')
        }
        
    except Exception as e:
        print(f"[ERROR FATAL] Falló el procesamiento de la imagen '{key}': {str(e)}")
        raise e