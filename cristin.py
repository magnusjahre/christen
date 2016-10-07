#! /usr/bin/python
# coding=utf8

import locale
import sys
import re
import time
import requests
from cgi import escape as html_escape
from urllib import urlopen
import xml.etree.ElementTree as ET
from optparse import OptionParser

filtercategories = ["FOREDRAG", "MEDIEBIDRAG", "KOMMERSIALISERIN", "PRODUKT"]
filtersubcategories = ["ARTIKKEL_POP", "KOMPENDIUM", "INTERVJU", "MASTERGRADSOPPG", "HOVEDFAGSOPPGAVE"]
typelist = ["html-onefile", "html-yearfiles", "console"]

L2_KEY = "LEVEL2"

printCategoryNames = {"BOKRAPPORTDEL": "Conference",
                      "TIDSSKRIFTPUBL": "Journal",
                      "RAPPORT": "PhD Thesis/Technical Report",
                      "BOK": "Book",
                      L2_KEY: "Cristin Level 2"}

printCategories = ["BOKRAPPORTDEL", "TIDSSKRIFTPUBL", "RAPPORT", "BOK", L2_KEY]

HTML_ONEFILE = 0
HTML_YEARFILE = 1
CONSOLE = 2

def parseArgs():
      
    parser = OptionParser(usage="usage: cristin.py [options] username [username ...]")
    parser.add_option("-o", "--outfile", dest="filename", default="papers.txt",
                  help="write output to FILE")
    parser.add_option("-t", "--output-type", dest="type", default=typelist[CONSOLE],
                  help="output type, alternatives "+str(typelist))
    parser.add_option("-p", "--pattern", dest="pattern", default="",
                  help="only include papers where the title matches PATTERN")
    parser.add_option("-y", "--year", dest="year", type="int", default=0,
                  help="only include papers after YEAR")
    parser.add_option("--statfile", dest="statfile", default="",
                  help="print paper statistics to STATFILE")
    parser.add_option("--all", dest="all", action="store_true", default=False,
                  help="Print all publications in the database (Default: only Cristin level 1 and 2)")
    parser.add_option("-l", "--language", dest="lang", default="en",
                  help="output language: 'no' or 'en'")
    

    (options, args) = parser.parse_args()

    if len(args) < 1:
        print "At least one username must be provided"
        print parser.usage
        sys.exit()
        
    if options.type not in typelist:
        print >> sys.stderr, u"Unknown type " + options.type + ", alternatives are " + str(typelist)
        sys.exit()

    if options.lang not in ('en', 'no'):
        print sys.stderr, u"Unknown language code: '%s'" % options.lang

    return options, args


def skipElement(element):

    pubtype = element.find("kategori").find("hovedkategori").find("kode").text
    pubsubtype = element.find("kategori").find("underkategori").find("kode").text

    skip = False
    for f in filtercategories:
        if pubtype == f:
            skip = True

    for f in filtersubcategories:
        if pubsubtype == f:
            skip = True

    return skip

class Author:

    def __init__(self, element):
        self.order = int(element.find("rekkefolgenr").text)
        self.firstname = unicode(element.find("fornavn").text)
        self.surname = unicode(element.find("etternavn").text)
    
    def dump(self):
        print str(self.order)+" "+self.firstname+" "+self.surname

class Paper:
    def __init__(self, element, categorydata, lang):
        self.year = int(element.find("ar").text)
        self.ident = int(element.find("id").text)
        self.title = element.find("tittel").text
        self.journal = ""
        self.level = 0

        self.type = element.find("kategori").find("hovedkategori").find("kode").text
        self.subtype = element.find("kategori").find("underkategori").find("kode").text
        
        if self.type == "TIDSSKRIFTPUBL":
            journaldata = categorydata.find("tidsskriftsartikkel").find("tidsskrift")
            self.journal = journaldata.find("navn").text
            qualitylevel = journaldata.find("kvalitetsniva")
            if qualitylevel != None:
                self.level = int(qualitylevel.find("kode").text.rstrip("A"))

        elif self.type == "BOKRAPPORTDEL":
            part = categorydata.find("bokRapportDel").find("delAv")
            comdata = part.find("forskningsresultat").find("fellesdata") 
            self.journal = comdata.find("tittel").text
            report = part.find("forskningsresultat").find("kategoridata").find("bokRapport")
            publisherdata = report.find("forlag")
            if publisherdata is None:
                publisherdata = report.find("serie")
                if publisherdata is not None:
                    qualitydata = publisherdata.find("kvalitetsniva")
            if publisherdata != None:
                qualitydata = publisherdata.find("kvalitetsniva")
                if qualitydata != None:
                    self.level = int(qualitydata.find("kode").text)

        elif self.type == "RAPPORT":
            if not (self.subtype == "DRGRADAVH" or self.subtype == "RAPPORT"):
                assert False, self.title+" is not a PhD Thesis or report"
            if self.subtype == "DRGRADAVH":
                self.journal = "Doktorgradsavhandling" if lang == 'no' else "Doctoral Dissertation"
                # This is a hack: PhD theses count towards RBO and thus should be included but are technically not level 1
                self.level = 1  
            else:
                text = "Teknisk rapport" if lang == 'no' else "Technical Report"
                try:
                    text += ": "+categorydata.find("bokRapport").find("utgiver").find("navn").text
                except:
                    pass
                self.journal = text
                    

        elif self.type == "BOK":
            forlag = categorydata.find("bokRapport").find("forlag")
            utgiver = categorydata.find("bokRapport").find("utgiver")
            
            if forlag != None:
                self.journal = forlag.find("navn").text
            elif utgiver != None:
                self.journal = utgiver.find("navn").text
            else:
                assert False, "Could not determine book publisher for title "+self.title
        else:
            print >> sys.stderr, (u"Unknown paper type %s for title %s" % (self.type, self.title)).encode('utf-8')

        authorelem = element.findall("person")
        self.authors = [None for i in range(len(list(authorelem)))]
        for a in list(authorelem):
            author = Author(a)
            self.authors[author.order-1] = author
        
        self.url = None
        ressurs = element.find("ressurs") 
        if ressurs != None:
            if ressurs.find("type").find("kode").text == "FULLTEKST":
                self.url = ressurs.find("url").text
    
    def replaceNorLetters(self, string):
        out = ""
        for s in string:
            if s == u'æ':
                out = out+"ae"
            elif s == u'Æ':
                out = out + "Ae"
            elif s == u"ø":
                out = out + "o"
            elif s == u"Ø":
                out = out + "O"
            elif s == u"å":
                out = out + "aa"
            elif s == u"Å":
                out = out + "Aa"
            else:
                out = out + s
        return out
    
    def dump(self):
        print str(self.year)
        print self.title
        for a in self.authors:
            a.dump()
    
    def getAuthorString(self, lang):
        outstr = self.authors[0].firstname + " " + self.authors[0].surname
        for a in self.authors[1:len(self.authors)-1]:
            outstr += ", " + a.firstname + " " + a.surname
        if len(self.authors) > 1:
            and_ = " og " if lang == 'no' else " and "
            outstr += and_ + self.authors[-1].firstname + " " + self.authors[-1].surname
        return outstr


    def printConsole(self, outfile, lang):
        print >> outfile, self.getAuthorString(lang).encode('utf-8')
        print >> outfile, self.title.encode('utf-8')
        print >> outfile, self.journal.encode('utf-8'), "(Level " + str(self.level) + ")",
        print >> outfile,""

    def printHTML(self, outfile, lang):
        print >> outfile, "<p>"
        print >> outfile, html_escape(self.getAuthorString(lang)).encode("utf-8") + "<br />"
        if self.url != None:
            # Check if the URL is OK before generating an HTML link.
            try:
                r = requests.head(self.url, timeout=5)
                # Uncomment the next line to print HTTP status codes for all URLs. 
                # print >> sys.stderr, r.status_code, self.url
                if r.status_code >= 400:
                    print >> sys.stderr, "URL '%s' failed with status code %d" % (self.url, r.status_code)
                else:
                    link = "<strong><a href='%s'>" % html_escape(self.url)
                    link += html_escape(self.title).encode("utf-8")
                    link += "</a></strong><br />"
                    print >> outfile, link
            except requests.exceptions.ConnectionError:
                print >> sys.stderr, "Connection refused for url '%s'" % self.url
            except requests.exceptions.RequestException:
                print >> sys.stderr, "Invalid URL: '%s'" % self.url
        else:
            print >> outfile, "<strong>" + html_escape(self.title).encode("utf-8") + "</strong><br />"
        print >> outfile, "<em>" + html_escape(self.journal).encode("utf-8") + "</em><br />"
        print >> outfile, "</p>"
        
    def __cmp__(self, other):
        if self.authors[0].surname == other.authors[0].surname:
            return cmp(self.ident, other.ident)
        return cmp(self.authors[0].surname, other.authors[0].surname)

def addPapers(name, papers, years, pt, addAllPapers, lang):
    url = "http://cristin.no/ws/hentVarbeiderPerson?"
    url += "navn="+name+"&"
    url += "eierkode=NTNU"

    print "Retriving papers for user %s" % name

    data = urlopen(url).read()
    try:
        element = ET.fromstring(data)
    except:
        print "Search for user "+name+" failed, continuing"
        return papers, years
    
    
    for resResult in list(element):
        if resResult.tag == "forskningsresultat":
            data = resResult.find("fellesdata")
            if not skipElement(data):
                categorydata = resResult.find("kategoridata")
                paper = Paper(data, categorydata, lang)
 
                if paper.ident not in papers:
                    if addAllPapers:
                        papers[paper.ident] = paper
                    else:
                        if paper.level > 0:
                            papers[paper.ident] = paper    

                if paper.year not in years:
                    years.append(paper.year)

    return papers, years

def printHTMLHeader(outfile, lang):
    print >> outfile, '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">'
    print >> outfile, '<html xmlns="http://www.w3.org/1999/xhtml">'
    print >> outfile, "<head>"
    print >> outfile, '<meta http-equiv="Content-Type" content="text/html; charset=utf-8" />'
    if lang == 'en':
        print >> outfile, "<title>Publications</title>"
    elif lang == 'no':
        print >> outfile, "<title>Publikasjoner</title>"
    print >> outfile, "</head>"
    print >> outfile, "<body>"
    
def printHTMLFooter(outfile, lang):
    if lang == 'en':
        text = "Publication list generated with data from "
    elif lang == 'no':
        text = "Publikasjonslista er laget med data hentet fra "
        locale.setlocale(locale.LC_TIME, "nb_NO")

    print >> outfile, text + "<p><small><a href='https://www.ntnu.no/cristin'>Cristin</a> " +\
                      time.strftime("%d. %B %Y").lstrip('0') + ".</small></p>"
    print >> outfile, "</body>"
    print >> outfile, "</html>"

def match(title, pattern):
    if pattern == "":
        return True
    
    if re.search(pattern, title, re.IGNORECASE) == None:
        return False
    return True

def matchcnt(year, papers, titlepattern):
    matches = 0
    for p in papers:
        if papers[p].year == year and match(papers[p].title, titlepattern):
            matches += 1
            
    return matches
                

def printPapers(papers, years, printtype, outfile, titlepattern, lang):
    if printtype == typelist[HTML_ONEFILE]:
        printHTMLHeader(outfile, lang)
    
    sortedpapers = sorted(papers.values())

    for y in years:
        if matchcnt(y, papers, titlepattern) == 0:
            continue
        
        if printtype == typelist[HTML_YEARFILE]:
            fname = str(y) + ".html"
            print "Writing data for year %s to file %s" % (y, fname)
            outfile = open(fname, "w")
        
        if printtype == typelist[HTML_ONEFILE] or printtype == typelist[HTML_YEARFILE]:
            print >> outfile, "<h2>%s</h2><div>" % y
        else:
            print>> outfile, y
        
        for paper in sortedpapers:
            if paper.year == y and match(paper.title, titlepattern):
                if printtype == typelist[HTML_ONEFILE] or printtype == typelist[HTML_YEARFILE]:
                    paper.printHTML(outfile, lang)
                else:
                    paper.printConsole(outfile, lang)

        if printtype == typelist[HTML_ONEFILE] or printtype == typelist[HTML_YEARFILE]:
            print >> outfile, "</div>"
        else:
            print >> outfile, ""
            
        if printtype == typelist[HTML_YEARFILE]:
            outfile.close()
            
    if printtype == typelist[HTML_ONEFILE]:
        printHTMLFooter(outfile, lang)

def printStatistics(statfilename, papers, startyear, printall):
    stats = getStatistics(papers, startyear, printall)
    categories = []
    for y in stats:
        for c in stats[y]:
            if c not in categories:
                categories.append(c)
    
    statfile = open(statfilename, "w")
    print >> statfile, "Year",
    for c in printCategories:
        print >> statfile, ";" + printCategoryNames[c],
    print >> statfile
    
    for y in sorted(stats.keys()):
        if y < startyear:
            continue
        
        print >> statfile, y,
        for c in printCategories:
            if c in stats[y]:
                print >> statfile, ";" + str(stats[y][c]),
            else:
                print >> statfile, ";0",
        print >> statfile
    
    statfile.close()
    

def getStatistics(papers, startyear, printall):
    stats = {}
    
    papercnt = 0
    l2cnt = 0
    
    for pid in papers:
        year = papers[pid].year
        ptype = papers[pid].type
        
        if year >= startyear and ptype != "RAPPORT":
            papercnt += 1
        
        if year not in stats:
            stats[year] = {}
            
        if ptype not in stats[year]:
            stats[year][ptype] = 0
        
        stats[year][ptype] += 1
        
        if L2_KEY not in stats[year]:
            stats[year][L2_KEY] = 0
            
        if papers[pid].level == 2:
            stats[year][L2_KEY] += 1
            if year >= startyear:
                l2cnt += 1
    
    if not printall:
        if papercnt != 0:
            l2rate = (float(l2cnt)/float(papercnt))*100
        else:
            l2rate = 0.0
        
        print "Statistics:", papercnt, "papers in total,", l2cnt, "at level 2 ("+ "%.1f" % l2rate +"%)"
    
    return stats

def main():

    opts, args = parseArgs()

    papers = {}
    years = []
    for name in args:
        papers, years = addPapers(name, papers, years, opts.type, opts.all, opts.lang)

    years.sort()
    if opts.year != 0:
        while years[0] < opts.year:
            years.pop(0)
    years.reverse()
    
    if opts.type == typelist[HTML_ONEFILE]:
        print "Writing output to file " + opts.filename
        outfile = open(opts.filename, "w")
    else:
        outfile = sys.stdout

    printPapers(papers, years, opts.type, outfile, opts.pattern, opts.lang)
    
    if outfile != sys.stdout:
        outfile.close()
    
    if opts.statfile != "":
        printStatistics(opts.statfile, papers, opts.year, opts.all)

if __name__ == "__main__":
    main()
