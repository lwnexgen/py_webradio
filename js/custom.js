var player = new Clappr.Player(
    {
	source: "http://***REMOVED***:***REMOVED***/webtune_live/101_5.m3u8",
	parentId: "#player",
	autoPlay: false,
	audioOnly: true,
	maxBufferLength: 180,
    }
);

var skipfwd = $('<input>', {
    'id': 'skipfwd1',
    'type': 'button',
    'value': '+1',
});

var skipbck = $('<input>', {
    'id': 'skipbck1',
    'type': 'button',
    'value': '-1',
});

skipbck.click(function() {
    player.seek(
	player.getCurrentTime() - 1
    )
});

skipfwd.click(function() {
    player.seek(
	player.getCurrentTime() + 1
    )
});

var skipfwd5 = $('<input>', {
    'id': 'skipfwd5',
    'type': 'button',
    'value': '+5',
});

var skipbck5 = $('<input>', {
    'id': 'skipbck5',
    'type': 'button',
    'value': '-5',
});

skipbck5.click(function() {
    player.seek(
	player.getCurrentTime() - 5
    )
});

skipfwd5.click(function() {
    player.seek(
	player.getCurrentTime() + 5
    )
});

$("#controls").append(skipbck10);
$("#controls").append(skipbck5);
$("#controls").append(skipbck);
$("#controls").append(skipfwd);
$("#controls").append(skipfwd5);
$("#controls").append(skipfwd10);

player.play()
