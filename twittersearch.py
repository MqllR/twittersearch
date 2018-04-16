#!/usr/bin/env python3

# -*- encoding: utf-8 -*-

import tweepy
import boto3
import os

from boto3.dynamodb.conditions import Key

consumer_key = os.environ['TWITTER_CONSUMER_KEY']
consumer_secret = os.environ['TWITTER_CONSUMER_SECRET']
access_token =  os.environ['TWITTER_ACCESS_TOKEN']
access_token_secret = os.environ['TWITTER_ACCESS_TOKEN_SECRET']
dynamo_table = os.environ['DYNANODB_TABLE']
sns_arn = os.environ['SNS_ARN']

def put_item(table, tweet_id, created_at, tags, tweet):
    try:
        table.put_item(
            Item={
                'tweetId': tweet_id,
                'tags': tags,
                'created_at': created_at,
                'tweet': tweet
            }    
        )
    except Exception as e:
        print('Aie to DynamoDB: {}'.format(str(e)))
        
def get_last_item(table):
    try:
        # --index-name "tags_index" --key-condition-expression "tags = :tags and created_at BETWEEN :date1 and :date2" --expression-attribute-values '{":tags": {"S": "ethereum"}, ":date1": {"S": "2018-03-26 15:35:00"}, ":date2": {"S": "2018-03-31 16:00:00"}}'
        items = table.query(
            IndexName="tags_index",
            ScanIndexForward=False,
            KeyConditionExpression=Key('tags').eq('ethereum') &
                                   Key('created_at').between('2018-03-31 06:00:00', '2018-03-31 08:00:00'),
            Limit=1
        )
        
        if items.get('Items'):
            return items['Items'][0]
        else:
            return False
    except Exception as e:
        print(e)
        
def twitter_search(last_tweet=None):
    
    auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
    auth.set_access_token(access_token, access_token_secret)
 
    api = tweepy.API(auth)
     
    results = [] 
    
    try:
        if last_tweet:
            for s in api.search(q='ethereum', count=100, since_id=int(last_tweet['tweetId'])):
                if s._json['retweet_count'] >= 500:
                    results.append(s)
        else:
            for s in api.search(q='ethereum', count=100):
                if s._json['retweet_count'] >= 500:
                    results.append(s)
            
        return results
    except Exception as e:
        print(str(e))


def handler(event, context):
    
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(dynamo_table)
    
    last_store_tweet = get_last_item(table)
    
    if last_store_tweet:
        print('Last tweet: {}'.format(last_store_tweet))
        res = twitter_search(last_store_tweet)
    else:
        res = twitter_search()
   
    try:
        if res:
            dynamodb = boto3.resource('dynamodb')
            table = dynamodb.Table(dynamo_table)
            
            for r in res:
                print('Write Tweet: {}'.format(r.id))
                put_item(table, r.id,
                                r.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                                "ethereum",
                               { 'text': r.text,
                                 'retweet_count': r._json['retweet_count'],
                                 'favorite_count': r._json['favorite_count'],
                               }
                        )

                res.append({
                    'text': r.text,
                    'retweet_count': r._json['retweet_count'],
                    'favorite_count': r._json['favorite_count'],
                    'created_at': r.created_at.strftime("%Y-%m-%d %H:%M:%S")
                })
        
        client = boto3.client('sns')
        
        msg = ""
        
        for r in res:
            msg += "{}\nRT: {}  FV: {}   Created At: {}\n\n".format(
                        r['text'],
                        r['retweet_count'],
                        r['favorite_count'],
                        r['created_at'])
                        
        client.publish(
            TopicArn=sns_arn,
            Message=msg
        )
        
        print('Notification sended')
            
    except Exception as e:
        print(e)