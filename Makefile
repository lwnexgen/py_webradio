deploy:
	rm -rf /var/www/html/webtune_live/{js,css,manifest*,tuner.html}
	cp -r js css tuner.html /var/www/html/webtune_live/

