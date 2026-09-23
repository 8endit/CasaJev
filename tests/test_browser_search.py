import pytest
from casajev.browser_search import direct_google_query,visible_search


@pytest.mark.parametrize('message,expected',[
    ('Google Python Dokumentation','Python Dokumentation'),
    ('Bitte suche bei Google nach IANA example domains.','IANA example domains'),
    ('Öffne die Suchergebnisse für „usb wifi“. Verändere nichts.','usb wifi'),
    ('Zeige mir die Suchergebnisse zu USB-C Hubs. Nur ansehen.','USB-C Hubs'),
    ('Google das bitte',None),('Google dies',None),('Erkläre Google',None)])
def test_explicit_search_query(message,expected):
    assert direct_google_query(message)==expected

class Browser:
    def __init__(self,links=True):self.calls=[];self.links=links
    def call(self,action,data=None):
        self.calls.append((action,data))
        page={'url':'https://www.google.com/search?q=test','title':'Google','text':'Test'}
        if action=='search_results':
            page['links']=[{'title':'Official source','url':'https://example.com'}] if self.links else []
        if action=='read_page':
            page={'url':data['url'],'title':'Source','text':'Actual source content'}
        return page

class Jev:
    last={'test':True}
    def __init__(self,action='open:0'):self.action=action;self.calls=0
    def ask(self,*args):self.calls+=1;return {'action':self.action}


def test_visible_search_only_opens_observed_choice():
    browser=Browser();jev=Jev();steps=[]
    result=visible_search(browser,jev,'Test','Find official Test',lambda *args:steps.append(args))
    assert result['selected']['url']=='https://example.com'
    assert [x[0] for x in browser.calls]==['navigate','search_results','read_page']
    assert len(steps)==3 and result['seconds']>=0
    assert result['page']['text']=='Actual source content'


def test_show_results_request_only_navigates_and_does_not_scrape_or_select():
    browser=Browser();jev=Jev();steps=[]
    result=visible_search(browser,jev,'usb wifi','Öffne die Suchergebnisse für usb wifi.',lambda *args:steps.append(args))
    assert [action for action,_data in browser.calls]==['navigate','status']
    assert browser.calls[0][1]['url'].startswith('https://html.duckduckgo.com/html/?')
    assert result['selected'] is None
    assert result['message']=='Die Suchtreffer sind im Browser geöffnet.'
    assert jev.calls==0

@pytest.mark.parametrize('action',[None,'open:99','buy','show_results'])
def test_uncertain_or_invalid_action_does_not_navigate(action):
    browser=Browser()
    result=visible_search(browser,Jev(action),'Test','Test',lambda *a:None)
    assert result['selected'] is None
    assert [x[0] for x in browser.calls]==['navigate','search_results']


def test_no_results_stops_without_model_or_bypass():
    browser=Browser(False);jev=Jev()
    result=visible_search(browser,jev,'Test','Test',lambda *a:None)
    assert jev.calls==0 and result['selected'] is None
    assert 'übernehmen' in result['message']


def test_google_access_check_stops_before_model_even_if_links_present():
    class BlockedBrowser(Browser):
        def call(self,action,data=None):
            page=super().call(action,data)
            page['url']='https://www.google.com/sorry/index?continue=test'
            return page
    browser=BlockedBrowser();jev=Jev()
    result=visible_search(browser,jev,'Test','Test',lambda *a:None)
    assert result['blocked']=='google_access_check'
    assert 'CAPTCHA' in result['message']
    assert jev.calls==0 and result['selected'] is None
    assert [x[0] for x in browser.calls]==['navigate','search_results']
