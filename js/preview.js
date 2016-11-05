function showdetail(itemID){
  var grid = document.getElementById(itemID);
  grid.style.display = "flex";
  grid.style.width = "100%" ;
}

function closedetail(itemID){
  var grid = document.getElementById(itemID);
  grid.style.width = "0%" ;
}

function changeBackground(str){
  var cover = document.getElementById("Cover");
  str = "url(img/" + str+ ")";
  cover.style.backgroundImage = str;
}
