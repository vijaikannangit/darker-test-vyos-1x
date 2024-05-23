<!-- include start from generic-interface-multi-broadcast.xml.i -->
<leafNode name="interface">
  <properties>
    <help>Interface to use</help>
    <completionHelp>
      <script>${vyos_completion_dir}/list_interfaces --broadcast</script>
    </completionHelp>
    <valueHelp>
      <format>txt</format>
      <description>Interface name</description>
    </valueHelp>
    <constraint>
      #include <include/constraint/interface-name.xml.i>
    </constraint>
    <multi/>
  </properties>
</leafNode>
<!-- include end -->
