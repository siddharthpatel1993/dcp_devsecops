from django.test import Client

def test_one():

    client = Client()
    response = client.get('/input')
    assert response.status_code == 200

def test_two():
    pass
    #client = Client()
    #response = client.get('/result1')
    #assert response.status_code == 200

def test_third():
    pass
    #client = Client()
    #response = client.get('/result2')
    #assert response.status_code == 200

def test_fourth():

    client = Client()
    response = client.get('/notes')
    assert response.status_code == 301

def test_fifth():

    client = Client()
    response = client.get('/chatbot')
    assert response.status_code == 301

