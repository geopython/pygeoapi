function submitJob(url) {
  var elms = document.getElementsByClassName('job-form-input');
  inputs = [];
  for (var i = 0; i < elms.length; i++) {
    inputs.push({id: elms[i].name, value: elms[i].value});
  }
  var request = new XMLHttpRequest();
  request.open('POST', url, true);
  request.setRequestHeader('Content-type', 'application/json');
  request.onreadystatechange = function() {
    if (this.readyState = this.DONE && request.status == 201) {
      if (this.onreadystatechange) {
        request.onreadystatechange = null;
      }
      var jobResultsSection = document.getElementById('job-results');
      jobResultsSection.innerHTML = '<h3>Results</h3>';
      var responseLocation = request.getResponseHeader("Location");

      var list = document.createElement('ul');
      jobResultsSection.appendChild(list);

      responseElements = [
        {'innerHTML': 'Job status', 'target': '#', 'href': responseLocation},
        {'innerHTML': 'Job output', 'target': '#', 'href': responseLocation + '/results'}
      ]

      responseElements.forEach(function(el) {
        var li = document.createElement('li');
        var a = document.createElement('a');
        Object.keys(el).forEach(function(prop) {
          a[prop] = el[prop]
        })
        li.appendChild(a);
        list.appendChild(li);
      })

      jobResultsSection.appendChild(list);

      return false
    }
  }
  data = {"inputs": inputs}
  request.send(JSON.stringify(data));
  return false;
}
