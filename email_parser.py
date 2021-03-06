import email.message, email.parser, email, json, re, email.utils, pickle, nltk,settings
from os import listdir
from time import strftime
from urllib2 import Request, urlopen

class Email(object):
    def __init__(self, email_path):
        '''Initializes an instance of the Email class.'''
        self.path = email_path
          
    def get_body(self):
        '''Stores the body of the email as an attribute, removing any whitespace characters and escapes.'''
        fp = open(self.path)   
        msg = email.message_from_file(fp)
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == 'text/plain':
                    self.body = remove_junk(str(part.get_payload(decode=True)))
                    if len(self.body) <= 16:
                        self.valid = False
                    return
        else:
            self.body = remove_junk(str(msg.get_payload(decode=True)))
            if len(self.body) <= 16:
                self.valid = False
            return
        
    def get_header(self):
        '''Gets header information from the email and stores it as attributes.'''
        fp = open(self.path)
        msg = email.message_from_file(fp)
        for item in msg.items():
            if item[0] == 'From':
                parsed_address = email.utils.parseaddr(item[1])
                self.name, encoding = email.Header.decode_header(parsed_address[0])[0]
                self.name = remove_non_ascii(self.name)
                self.address = parsed_address[1]
                if "google.com" in self.address or "Google.com" in self.address or "pols.exp@gmail.com" in self.address:
                    self.valid = False
                    return
                else:
                    self.valid = True
            if item[0] == 'Date':
                self.date = strftime('%m/%d/%Y',email.utils.parsedate(item[1]))
                self.month = strftime('%m',email.utils.parsedate(item[1]))
                self.year = strftime('%Y',email.utils.parsedate(item[1]))
            if item[0] == 'Subject':
                if item[1].startswith("=?utf-8?") or item[1].startswith("=?UTF-8?"):
                    self.subject, encoding2 = email.Header.decode_header(item[1])[0]
                    self.subject = remove_non_ascii(self.subject)
                    # ^^^ breaks program when encounters subject encoded with "iso-8859"
                else:
                    self.subject = item[1]
                    #self.subject = remove_non_ascii(self.subject)
   
    def get_info(self):
        '''Returns a dictionary containing the api information of the sender of an email.'''
        for member in self.congress:
            if member['person']['lastname'] in self.name:
                if member['person']['firstname'] in self.name:
                #if the last name and first name/nick name are in self.name: get self.party
                    return pull_api_info(member)
                elif member['person']['nickname']:
                    if member['person']['nickname'] in self.name:
                        return pull_api_info(member)
        #If the first loop didn't classify the email, search instead for just the first two letters
        #of the first name, along with the full last name.
        for member in self.congress:
            if member['person']['lastname'] in self.name:
                if member['person']['firstname'][:2] in self.name:
                    return pull_api_info(member)
        #If neither loop got the information, look just for the last name.
        for member in self.congress:
            if member['person']['lastname'] in self.name:
                return pull_api_info(member)
        
    def construct_dict(self,classifier):
        '''Constructs a dictionary of email information.'''
        self.get_header()
        self.get_body()
        if self.valid == False:
            return False
        try:
            email_dict = self.get_info()
            #email_dict = {'party':email_dict_temp['party'],'title_long':email_dict_temp['title_long']}
            email_dict['Subject'] = self.subject
            email_dict['Name'] = self.name
            email_dict['Address'] = self.address
            email_dict['Date'] = self.date
            email_dict['Body'] = self.body
            email_dict['Month'] = self.month
            email_dict['Year'] = self.year
            if classifier:
                if settings.extractor['use_extractor']:
                    trimmed_txt = word_extractor(self.body)
                    email_dict['assignment'] = classifier.classify(wordlist(trimmed_txt))
                else:
                    email_dict['assignment'] = classifier.classify(wordlist(self.body))
            #email_dict['assignment'] = '1'
            return email_dict
        except:
            return None
        
class Directory(Email):
    def __init__(self,directory):
        '''Initializes an instance of the Directory class.'''
        self.directory = directory
        self.congress = api_call()
        if settings.classifier['use_classifier']:
            self.classifier = load_pickle(settings.classifier['classifier_fp'])
        else:
            self.classifier = None
        
    def dir_list(self):
        '''Returns the list of all files in self.directory'''
        try:
            return listdir(self.directory)
        except WindowsError as winErr:
            print("Directory error: " + str((winErr)))
        
    def dir_dict(self):
        '''Constructs a list of email dictionaries
        from a directory of .eml files.'''
        eml_list = []
        for email in self.dir_list():
            self.path = self.directory + '/' + email
            eml_dict = self.construct_dict(self.classifier)
            if eml_dict:
                eml_list.append(eml_dict)
        return eml_list
        
    def convert_json(self, json_path):
        '''Creates a json file of email information at the specified path.'''
        with open(json_path,'w') as json_file:
            json.dump(self.dir_dict(),json_file)
        
def remove_junk(string):
    '''Removes whitespace characters, escapes, and links from a string.'''
    string = re.sub(r'\s+', ' ', string)
    string = re.sub(r"[\x80-\xff]", '', string)
    link_regex=["<http.*?>","http.*? ","http.*?[^\s]\.gov","http.*?[^\s]\.com","http.*?[^\s]\.COM",
                "www.*?[^\s]\.com","www.*?[^\s]\.org","www.*?[^\s]\.net","www.*?[^\s]\.gov","/.*?[^\s]\.com",
                "/.*?[^\s]\.COM","/.*?[^\s]\.gov",",.*?[^\s]\.gov",",.*?[^\s]\.com",
                "<.*?>"]
    for curr in link_regex:
        string = re.sub(curr,'',string)
    return string

def remove_non_ascii(text):
    '''Removes any non-ascii characters from a string.'''
    return ''.join(i for i in text if ord(i)<128)

def word_extractor(text, keyword=settings.extractor['keyword'], n=settings.extractor['str_length']):
    '''Extracts n words before and after the keyword in a given text.'''
    text = text.lower()
    separated = text.partition(keyword)
    if separated[2]:
        neg = -1*n
        before,after = separated[0].split()[neg:],separated[2].split()[:n]
        before.extend(after)
        return ' '.join(before)
    else:
        return text

def wordlist(text):
    '''Returns a list of words in the text.'''
    words = {}
    separated = separate(text)
    for word in separated:
        if word not in words.keys():
            words[word] = 1
    return words

def api_call():
    '''Makes an api call and returns a JSOn object of information on the current US congress.'''
    request = Request('https://www.govtrack.us/api/v2/role?sort=-enddate&limit=2019')
    return json.load(urlopen(request))['objects']

def pull_api_info(entry):
        '''Returns a dictionary of all the info from the API call.'''
        info_dict = {}
        for key in entry:
            if key == 'person':
                for person_key in entry[key]:
                    info_dict[person_key] = entry[key][person_key]
            else:        
                info_dict[key] = entry[key]
        return info_dict

def separate(text):
    '''Takes text and separates it into a list of words'''
    alphabet = 'abcdefghijklmnopqrstuvwxyz'
    stop_list = stopwords()
    words = text.split()
    standardwords = []
    for word in words:
        if word not in stop_list:
            newstr = ''
            for char in word:
                if char.lower() in alphabet:
                   newstr += char
            if newstr != '':
                standardwords.append(newstr)
    return map(lambda x: x.lower(),standardwords)
    
def load_pickle(pickle_fp):
    '''Loads a .pickle file and returns the object.'''
    f = open(pickle_fp,'rb')
    content = pickle.load(f)
    f.close()
    return content

def stopwords(stopwords_fp=settings.stopwords_fp):
    '''Returns a list of stopwords from the given stopwords file.'''
    with open(stopwords_fp) as f:
        content = f.readlines()
    lines = [line.rstrip() for line in content]
    return lines

def main():
    '''Guides the user through the program.'''
    directory = raw_input('Please enter the path to the directory of .eml files: ')
    d = Directory(directory)
    json_fp = raw_input('Please enter the location of the json file you would like to create: ')
    d.convert_json(json_fp)

 
if __name__ == '__main__':
    main()
