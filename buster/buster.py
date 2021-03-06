"""Ghost Buster. Static site generator for Ghost.

Usage:
  buster.py setup [--gh-repo=<repo-url>] [--dir=<path>]
  buster.py generate [--domain=<local-address>] [--dir=<path>] [--no-assets-versioning] [--rss-summaries] [--create-sitemap] [--site-url=<URL>]
  buster.py preview [--dir=<path>]
  buster.py deploy [--dir=<path>]
  buster.py add-domain <domain-name> [--dir=<path>]
  buster.py (-h | --help)
  buster.py --version

Options:
  -h --help                 Show this screen.
  --version                 Show version.
  --dir=<path>              Absolute path of directory to store static pages.
  --domain=<local-address>  Address of local ghost installation [default: local.tryghost.org].
  --gh-repo=<repo-url>      URL of your gh-pages repository.
  --no-assets-versioning    Remove version info from the filename of assets.
  --rss-summaries           Show only summaries in the rss feed
  --create-sitemap          Generate an xml site map
  --site-url=<URL>          URL of the website
"""

import os
import re
import sys
import shutil
import platform
import SocketServer
import SimpleHTTPServer
import xml.etree.ElementTree as ElementTree
from docopt import docopt
from datetime import date
from time import gmtime, strftime
from git import Repo


def main():
    arguments = docopt(__doc__, version='0.1.2')
    if arguments['--dir'] is not None:
        static_path = arguments['--dir']
    else:
        static_path = os.path.join(os.getcwd(), 'static')

    if arguments['generate']:
        if platform.system() == "Windows":
            command = ("wget "
                       "--recursive "             # follow links to download entire site
                       "--convert-links "         # make links relative
                       "--page-requisites "       # grab everything: css / inlined images
                       "--no-parent "             # don't go to parent level
                       "--directory-prefix {1} "  # download contents to static/ folder
                       "--no-host-directories "   # don't create domain named folder
                       "{0}").format(arguments['--domain'], static_path)
        else:
            command = ("wget \\"
                   "--recursive \\"             # follow links to download entire site
                   "--convert-links \\"         # make links relative
                   "--page-requisites \\"       # grab everything: css / inlined images
                   "--no-parent \\"             # don't go to parent level
                   "--directory-prefix {1} \\"  # download contents to static/ folder
                   "--no-host-directories \\"   # don't create domain named folder
                   "{0}").format(arguments['--domain'], static_path)

        os.system(command)

        no_versioning = False
        if arguments["--no-assets-versioning"]:
            no_versioning = True
            versioned_assets = []

        # remove query string since Ghost 0.4
        file_regex = re.compile(r'.*?(\?.*)')
        for root, dirs, filenames in os.walk(static_path):
            for filename in filenames:
                if file_regex.match(filename):
                    newname = re.sub(r'\?.*', '', filename)
                    print "Rename", filename, "=>", newname
                    os.rename(os.path.join(root, filename), os.path.join(root, newname))

                if no_versioning and ("@v=" in filename):
                    versioned_assets.append(filename)

        if no_versioning:
            for root, dirs, filenames in os.walk(static_path):
                for filename in filenames:
                    data = None
                    with open(os.path.join(root, filename), 'r') as open_file:
                        data = open_file.read()
                    for asset_file in versioned_assets:
                        new_filename = asset_file.split("@v=", 1)[0]
                        data = data.replace(asset_file, new_filename)
                    with open(os.path.join(root, filename), 'w') as open_file:
                        open_file.write(data)
                    if filename in versioned_assets:
                        os.rename(os.path.join(root, filename), os.path.join(root, filename.split("@v=", 1)[0]))

        if arguments["--create-sitemap"]:
            if arguments['--site-url']:
                site_url = arguments['--site-url']
            else:
                site_url = raw_input("Enter the website URL: ").strip()
            if not ("http" in site_url):
                site_url = "http://" + site_url

            date_today = date.today()
            site_map = ""
            site_map_header = "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">\n"
            site_map_footer = "</urlset>"
            for root, dirs, filenames in os.walk(static_path):
                for filename in filenames:
                    if ".html" in filename:
                        section = "    <url>\n"
                        section = section + "        <loc>" + site_url + (root[len(static_path):]+"\\"+filename).replace("\\","/") + "</loc>\n"
                        section = section + "        <lastmod>%04d-%02d-%02d</lastmod>\n" % (date_today.year, date_today.month, date_today.day)
                        section = section + "        <changefreq>monthly</changefreq>\n"
                        section = section + "    </url>\n"
                        site_map = site_map + section
                        
            site_map = site_map_header + site_map + site_map_footer
            with open(static_path + "\\sitemap.xml", 'w') as file_sitemap:
                file_sitemap.write(site_map)
                file_sitemap.close()

        if arguments["--rss-summaries"]:
            original_escape_cdata = ElementTree._escape_cdata
            def _escape_cdata(text, encoding):
                if "<![CDATA[" in text:
                    try:
                        return text.encode(encoding, "xmlcharrefreplace")
                    except (TypeError, AttributeError):
                        ElementTree._raise_serialization_error(text)
                else:
                    return original_escape_cdata(text, encoding)
            ElementTree._escape_cdata = _escape_cdata
                        
            for root, dirs, filenames in os.walk(static_path):
                if root.rsplit("\\", 1)[1] == "rss":
                    tree = ElementTree.parse(os.path.join(root, filename))
                    xml_root = tree.getroot()
                    is_title = True
                    for description in xml_root.iter("description"):
                        if is_title:
                            is_title = False
                        else:
                            summary = description.text
                            #modify the summary
                            summary = " ".join(summary.split()[:50]) + " ..."
                            
                            #limit summary to one paragraph
                            if "<p>" in summary:
                                summary = summary.split("</p>",1)[0]
                                summary = summary + "</p>"
                            summary = "<![CDATA[" + summary + "]]>"

                            description.text = summary
                    tree.write(os.path.join(root, filename))

    elif arguments['preview']:
        os.chdir(static_path)

        Handler = SimpleHTTPServer.SimpleHTTPRequestHandler
        httpd = SocketServer.TCPServer(("", 9000), Handler)

        print "Serving at port 9000"
        # gracefully handle interrupt here
        httpd.serve_forever()

    elif arguments['setup']:
        if arguments['--gh-repo']:
            repo_url = arguments['--gh-repo']
        else:
            repo_url = raw_input("Enter the Github repository URL:\n").strip()

        # Create a fresh new static files directory
        if os.path.isdir(static_path):
            confirm = raw_input("This will destroy everything inside static/."
                                " Are you sure you want to continue? (y/N)").strip()
            if confirm != 'y' and confirm != 'Y':
                sys.exit(0)
            shutil.rmtree(static_path)

        # User/Organization page -> master branch
        # Project page -> gh-pages branch
        branch = 'gh-pages'
        regex = re.compile(".*[\w-]+\.github\.(?:io|com).*")
        if regex.match(repo_url):
            branch = 'master'

        # Prepare git repository
        repo = Repo.init(static_path)
        git = repo.git

        if branch == 'gh-pages':
            git.checkout(b='gh-pages')
        repo.create_remote('origin', repo_url)

        # Add README
        file_path = os.path.join(static_path, 'README.md')
        with open(file_path, 'w') as f:
            f.write('# Blog\nPowered by [Ghost](http://ghost.org) and [Buster](https://github.com/axitkhurana/buster/).\n')

        print "All set! You can generate and deploy now."

    elif arguments['deploy']:
        repo = Repo(static_path)
        repo.git.add('.')

        current_time = strftime("%Y-%m-%d %H:%M:%S", gmtime())
        repo.index.commit('Blog update at {}'.format(current_time))

        origin = repo.remotes.origin
        repo.git.execute(['git', 'push', '-u', origin.name,
                         repo.active_branch.name])
        print "Good job! Deployed to Github Pages."

    elif arguments['add-domain']:
        repo = Repo(static_path)
        custom_domain = arguments['<domain-name>']

        file_path = os.path.join(static_path, 'CNAME')
        with open(file_path, 'w') as f:
            f.write(custom_domain + '\n')

        print "Added CNAME file to repo. Use `deploy` to deploy"

    else:
        print __doc__

if __name__ == '__main__':
    main()
