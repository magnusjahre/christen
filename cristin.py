#!/usr/bin/python
# coding=utf8

# Copyright (c) 2015, Norwegian University of Science and Technology (NTNU)
# All rights reserved.
# 
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * Neither the name of NTNU nor the names of its contributors may be used 
#       to endorse or promote products derived from this software without 
#       specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL NTNU BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import sys
import re
import time
from urllib import urlopen
import xml.etree.ElementTree as ET
from optparse import OptionParser

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
    parser.add_option("-o", "--outfile", dest="filename", default="papers.php",
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
    

    (options, args) = parser.parse_args()

    if len(args) < 1:
        print "At least one username must be provided"
        print parser.usage
        sys.exit()
        
    if options.type not in typelist:
        print "Unknown type "+options.type+", alternatives are "+str(typelist)
        sys.exit()

    return options, args

class Author:

    def __init__(self, element):
        self.order = int(element.find("rekkefolgenr").text)
        self.firstname = unicode(element.find("fornavn").text)
        self.surname = unicode(element.find("etternavn").text)
    
    def dump(self):
        print str(self.order)+" "+self.firstname+" "+self.surname

class Paper:
    def __init__(self, element, categorydata):
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
                self.level = int(qualitylevel.find("kode").text)
            self.journal = self.journal.replace(" = Lecture notes in artificial intelligence", "")

        elif self.type == "BOKRAPPORTDEL":
            part = categorydata.find("bokRapportDel").find("delAv")
            comdata = part.find("forskningsresultat").find("fellesdata") 
            self.journal = comdata.find("tittel").text
            publisherdata = part.find("forskningsresultat").find("kategoridata").find("bokRapport").find("forlag")
            if publisherdata != None:
                qualitydata = publisherdata.find("kvalitetsniva")
                if qualitydata != None:
                    self.level = int(qualitydata.find("kode").text)

        elif self.type == "RAPPORT":
            if self.subtype == "DRGRADAVH":
                self.journal = "Doctoral Dissertation at NTNU"
                # This is a hack: PhD theses count towards RBO and thus should be included but are technically not level 1
                self.level = 1  
            elif self.subtype == "RAPPORT":
                text = "Technical Report"
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
    
    def getAuthorString(self):
        outstr = self.authors[0].firstname+" "+self.authors[0].surname
        for a in self.authors[1:len(self.authors)-1]:
            outstr += ", "+a.firstname+" "+a.surname
        if len(self.authors) > 1:
            outstr += " and "+self.authors[-1].firstname+" "+self.authors[-1].surname
        return outstr


    def printConsole(self, outfile):
        print >> outfile, self.getAuthorString()
        print >> outfile, self.title
        print >> outfile, self.journal, "(Level "+str(self.level)+")",
        print >> outfile,""

    def printHTML(self, outfile):
        print >> outfile, self.getAuthorString().encode("utf-8")+"<br>"
        if self.url != None:
            print >> outfile,  "<b><a href="+self.url+">"+self.title.encode("utf-8")+"</a></b><br>"
        else:
            print >> outfile,  "<b>"+self.title.encode("utf-8")+"</b><br>"
        print >> outfile,  self.journal.encode("utf-8")+"<br>"
        print >> outfile,  "<br>"
        
    def __cmp__(self, other):
        if self.authors[0].surname == other.authors[0].surname:
            return cmp(self.ident, other.ident)
        return cmp(self.authors[0].surname, other.authors[0].surname)

def addPapers(name, papers, years, pt, addAllPapers):
    url = "http://cristin.no/ws/hentVarbeiderPerson?"
    url += "navn="+name+"&"
    url += "eierkode=NTNU"

    print "Retriving papers for user "+name+" at url "+url+"..."

    data = urlopen(url).read()
    try:
        element = ET.fromstring(data)
    except:
        print "Search for user "+name+" failed, continuing"
        return papers, years
    
    
    for resResult in list(element):
        if resResult.tag == "forskningsresultat":
            data = resResult.find("fellesdata")
            categorydata = resResult.find("kategoridata")
            paper = Paper(data, categorydata)
            
            if paper.ident not in papers:
                if addAllPapers:
                    papers[paper.ident] = paper
                else:
                    if paper.level > 0:
                        papers[paper.ident] = paper    

            if paper.year not in years:
                years.append(paper.year)

    return papers, years

def printHTMLHeader(outfile):
    print >> outfile, "<html>"
    print >> outfile, "<head>"
    print >> outfile, "<title>Publications</title>"
    print >> outfile, '<meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>'
    print >> outfile, "</head>"
    print >> outfile, "<body>"
    
def printHTMLFooter(outfile):
    print >> outfile,"<i>Publication list generated "+time.strftime("%d.%m.%Y %H:%M")+"</i><br><br>"
    print >> outfile,"</body>"
    print >> outfile,"</html>"

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
                

def printPapers(papers, years, printtype, outfile, titlepattern):
    if printtype == typelist[HTML_ONEFILE]:
        printHTMLHeader(outfile)
    
    sortedpapers = sorted(papers.values())

    for y in years:
        if matchcnt(y, papers, titlepattern) == 0:
            continue
        
        if printtype == typelist[HTML_YEARFILE]:
            fname = str(y)+".html"
            print "Writing data for year "+str(y)+" to file "+fname
            outfile = open(fname, "w")
        
        if printtype == typelist[HTML_ONEFILE] or printtype == typelist[HTML_YEARFILE]:
            print >> outfile, '<b style="font-size: 12pt">'+str(y)+'</b><br><br><i>'
        else:
            print>> outfile, y
        
        for paper in sortedpapers:
            if paper.year == y and match(paper.title, titlepattern):
                if printtype == typelist[HTML_ONEFILE] or printtype == typelist[HTML_YEARFILE]:
                    paper.printHTML(outfile)
                else:
                    paper.printConsole(outfile)

        if printtype == typelist[HTML_ONEFILE] or printtype == typelist[HTML_YEARFILE]:
            print >> outfile, "</i><br>"
        else:
            print >> outfile, ""
            
        if printtype == typelist[HTML_YEARFILE]:
            outfile.close()
            
    if printtype == typelist[HTML_ONEFILE]:
        printHTMLFooter(outfile)

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
        print >> statfile, ";"+printCategoryNames[c],
    print >> statfile
    
    for y in sorted(stats.keys()):
        if y < startyear:
            continue
        
        print >> statfile, y,
        for c in printCategories:
            if c in stats[y]:
                print >> statfile, ";"+str(stats[y][c]),
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
        papers, years = addPapers(name, papers, years, opts.type, opts.all)

    years.sort()
    if opts.year != 0:
        while years[0] < opts.year:
            years.pop(0)
    years.reverse()
    
    if opts.type == typelist[HTML_ONEFILE]:
        print "Writing output to file "+opts.filename
        outfile = open(opts.filename, "w")
    else:
        outfile = sys.stdout

    printPapers(papers, years, opts.type, outfile, opts.pattern)
    
    if outfile != sys.stdout:
        outfile.close()
    
    if opts.statfile != "":
        printStatistics(opts.statfile, papers, opts.year, opts.all)

if __name__ == "__main__":
    main()
