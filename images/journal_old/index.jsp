<?xml version="1.0"?>
<!DOCTYPE wml PUBLIC "-//WAPFORUM//DTD WML 1.1//EN" "http://www.wapforum.org/DTD/wml_1.1.xml">





<wml>

<card title="&#x6613;&#x90ae;&#x90ae;&#x5c40;">

<p>

&#x8f93;&#x5165;&#x7528;&#x6237;&#x540d;&#x53ca;&#x5bc6;&#x7801;<br/>
&#x7528;&#x6237;&#x540d;:<input name="ID"  value="zhangzhen"  />@<input name="HN" value="mail.dlut.edu.cn"  />
&#x5bc6;&#x7801;:<input name="PWD"  value=""  />
</p>
<p>
<anchor>
&#x767b;&#x5f55;
<go href="http://wapmail.dlut.edu.cn/login_submit.jsp" method="post">
  <postfield name="username" value="$ID" />
  <postfield name="checkCodeGB" value="&#x4e2d;&#x6587;" />
  <postfield name="hostname" value="$HN" />
  <postfield name="password" value="$PWD" />
  <postfield name="redirectStr" value="maillist.jsp" />
  <postfield name="doLogin" value="true" />
</go>
</anchor>



<a href="register.jsp">&#x6ce8;&#x518c;</a><br/>

</p>
</card>
</wml>
